from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from accounts.audit import log_action
from accounts import rbac
from accounts.permissions import IsActiveEmployee, require

from .models import Department, EmployeeProfile, WorkSchedule
from .serializers import DepartmentSerializer, EmployeeSerializer, WorkScheduleSerializer


class EmployeeViewSet(viewsets.ModelViewSet):
    """
    Ro'yxatni ko'rish: `employees.view` (boshqa bo'limlarda xodim tanlashi kerak bo'lganlarga esa faqat
    ism/lavozim/bo'lim). Qo'shish va o'zgartirish: `employees.manage`. Oddiy xodim o'z ma'lumotini
    /api/auth/me/ orqali oladi — bu yerdan boshqalarga kira olmaydi (backendda 403).
    """

    serializer_class = EmployeeSerializer
    # Xodim tanlash kerak bo'ladigan bo'limlar (filtr, topshiriq berish, bonus va hokazo)
    PICKER = ("employees.view", "attendance.view", "tasks.view", "tasks.manage", "bonuses.view", "bonuses.manage",
              "discipline.view", "discipline.manage", "reports.view")

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [require(*self.PICKER)()]
        return [require("employees.manage")()]

    def _guard_target(self, obj):
        """Administrator bo'lmagan boshqaruvchi administratorni yoki o'zidan yuqori huquqli xodimni o'zgartira olmaydi."""
        me = self.request.user.profile
        if me.is_admin:
            return
        mine = set(me.effective_permissions())
        if obj.pk == me.pk:
            raise PermissionDenied("O'zingizni bu yerdan o'zgartira olmaysiz. Parolni Profil bo'limida almashtiring.")
        if obj.is_admin or not set(rbac.normalize(obj.permissions)) <= mine:
            raise PermissionDenied("Bu xodimni o'zgartirish uchun huquqingiz yetarli emas.")

    def get_queryset(self):
        qs = EmployeeProfile.objects.select_related("user", "department", "schedule", "face_profile")
        p = self.request.query_params
        search = p.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(full_name__icontains=search) | Q(position__icontains=search)
                | Q(department__name__icontains=search) | Q(user__username__icontains=search)
            )
        if p.get("department"):
            qs = qs.filter(department_id=p["department"])
        if p.get("position"):
            qs = qs.filter(position__icontains=p["position"])
        if p.get("role") in dict(EmployeeProfile.Role.choices):
            qs = qs.filter(role=p["role"])
        if p.get("is_active") in ("true", "false"):
            qs = qs.filter(is_active=p["is_active"] == "true")
        return qs.order_by("full_name")

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, "employee.create", obj, {
            "full_name": obj.full_name, "role": obj.role, "permissions": rbac.normalize(obj.permissions),
        })

    def perform_update(self, serializer):
        self._guard_target(serializer.instance)
        before_role = serializer.instance.role
        before_active = serializer.instance.is_active
        before_perms = rbac.normalize(serializer.instance.permissions)
        # Administrator o'zini faolsizlantira yoki rolini tushira olmasin (tizimdan bloklanib qolmaslik uchun)
        if serializer.instance.pk == self.request.user.profile.pk:
            data = serializer.validated_data
            if data.get("is_active") is False or data.get("role", before_role) != "admin":
                raise ValidationError({"detail": "O'zingizni faolsizlantira yoki rolingizni o'zgartira olmaysiz."})
        obj = serializer.save()
        details = {"fields": sorted(k for k in serializer.validated_data if k != "password")}
        if "password" in serializer.validated_data:
            details["password_changed"] = True
        if obj.role != before_role:
            details["role"] = [before_role, obj.role]
        if obj.is_active != before_active:
            details["is_active"] = [before_active, obj.is_active]
        after_perms = rbac.normalize(obj.permissions)
        if after_perms != before_perms:
            details["permissions"] = {"added": sorted(set(after_perms) - set(before_perms)),
                                      "removed": sorted(set(before_perms) - set(after_perms))}
        log_action(self.request, "employee.update", obj, details)

    def destroy(self, request, *args, **kwargs):
        """
        Standart: faolsizlantirish (tarix saqlanadi).
        `?permanent=true` — bazadan to'liq o'chirish (davomat, vazifa, bonus tarixi ham o'chadi).
        """
        obj = self.get_object()
        if obj.pk == request.user.profile.pk:
            return Response({"detail": "O'zingizni o'chira olmaysiz."}, status=status.HTTP_400_BAD_REQUEST)
        self._guard_target(obj)
        if request.query_params.get("permanent") == "true":
            if not request.user.profile.is_admin:
                raise PermissionDenied("Xodimni butunlay o'chirish faqat administrator uchun.")
            details = {"full_name": obj.full_name}
            user = obj.user
            pk = obj.pk
            obj.delete()
            user.delete()
            log_action(request, "employee.delete", details={**details, "id": pk})
        else:
            obj.is_active = False
            obj.save(update_fields=["is_active"])
            obj.user.is_active = False
            obj.user.save(update_fields=["is_active"])
            log_action(request, "employee.deactivate", obj, {"full_name": obj.full_name})
        return Response(status=status.HTTP_204_NO_CONTENT)


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        # Ro'yxatni formalar uchun har bir faol xodim ko'ra oladi; o'zgartirish faqat admin.
        if self.action in ("list", "retrieve"):
            return [IsActiveEmployee()]
        return [require("settings.manage")()]

    def get_queryset(self):
        return Department.objects.annotate(employee_count=Count("employees")).order_by("name")

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, "department.create", obj, {"name": obj.name})

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, "department.update", obj, {"name": obj.name})

    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        try:
            name, pk = obj.name, obj.pk
            obj.delete()
        except ProtectedError:
            return Response(
                {"detail": "Bu bo'limda xodimlar bor. Avval ularni boshqa bo'limga o'tkazing."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        log_action(request, "department.delete", details={"name": name, "id": pk})
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkScheduleViewSet(viewsets.ModelViewSet):
    queryset = WorkSchedule.objects.order_by("name")
    serializer_class = WorkScheduleSerializer

    def get_permissions(self):
        # Xodim formasi uchun jadvallar ro'yxatini xodim qo'sha oladiganlar ham ko'radi; o'zgartirish: settings.manage
        if self.action in ("list", "retrieve"):
            return [require("settings.manage", "employees.manage", "employees.view")()]
        return [require("settings.manage")()]

    def perform_create(self, serializer):
        obj = serializer.save()
        log_action(self.request, "schedule.create", obj, {"name": obj.name})

    def perform_update(self, serializer):
        obj = serializer.save()
        log_action(self.request, "schedule.update", obj, {"name": obj.name})

    def perform_destroy(self, instance):
        log_action(self.request, "schedule.delete", details={"name": instance.name, "id": instance.pk})
        instance.delete()  # xodimlarda schedule SET_NULL bo'ladi

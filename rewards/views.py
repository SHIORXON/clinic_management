from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.audit import log_action
from accounts.permissions import IsActiveEmployee, sees_all
from notifications.services import notify

from .models import Bonus, DisciplinaryRecord
from .serializers import BonusSerializer, DisciplineSerializer


def _fmt(n):
    return f"{int(n):,}".replace(",", " ") + " so'm"


class _RewardViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin, mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """O'chirish yo'q: xato yozuv bekor qilinadi (tarix saqlanadi). Xodim faqat o'zining bekor qilinmaganlarini ko'radi."""

    permission_classes = [IsActiveEmployee]
    model = None
    audit_prefix = ""
    perm_prefix = ""
    link = ""

    def get_queryset(self):
        me = self.request.user.profile
        qs = self.model.objects.select_related("employee", "employee__department", "created_by")
        if not sees_all(self.request, self.perm_prefix):
            return qs.filter(employee=me, is_cancelled=False)
        p = self.request.query_params
        if p.get("employee"):
            qs = qs.filter(employee_id=p["employee"])
        if p.get("department"):
            qs = qs.filter(employee__department_id=p["department"])
        if p.get("date_from"):
            qs = qs.filter(date__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(date__lte=p["date_to"])
        if p.get("search"):
            qs = qs.filter(employee__full_name__icontains=p["search"].strip())
        if p.get("cancelled") not in ("1", "true"):
            qs = qs.filter(is_cancelled=False)
        return qs

    def filter_queryset(self, qs):
        # Xodim uchun ham sana oralig'i
        p = self.request.query_params
        if not sees_all(self.request, self.perm_prefix):
            if p.get("date_from"):
                qs = qs.filter(date__gte=p["date_from"])
            if p.get("date_to"):
                qs = qs.filter(date__lte=p["date_to"])
        return qs

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except (ValueError, TypeError):
            return Response({"detail": "Sana formati YYYY-MM-DD bo'lishi kerak."}, status=400)

    def _deny(self, request):
        if not request.user.profile.can(f"{self.perm_prefix}.manage"):
            return Response({"detail": "Bu amal uchun sizda ruxsat yo'q."}, status=403)

    def create(self, request, *args, **kwargs):
        return self._deny(request) or self._create(request)

    def _create(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        obj = ser.save(created_by=request.user.profile)
        self.on_change(request, obj, "create")
        return Response(self.get_serializer(obj).data, status=201)

    def update(self, request, *args, **kwargs):
        denied = self._deny(request)
        if denied:
            return denied
        obj = self.get_object()
        if obj.is_cancelled:
            return Response({"detail": "Bekor qilingan yozuvni tahrirlab bo'lmaydi."}, status=400)
        ser = self.get_serializer(obj, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        obj = ser.save(updated_by=request.user.profile)
        self.on_change(request, obj, "update")
        return Response(self.get_serializer(obj).data)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        denied = self._deny(request)
        if denied:
            return denied
        obj = self.get_object()
        if obj.is_cancelled:
            return Response({"detail": "Yozuv allaqachon bekor qilingan."}, status=400)
        obj.is_cancelled = True
        obj.updated_by = request.user.profile
        obj.save()
        self.on_change(request, obj, "cancel")
        return Response(self.get_serializer(obj).data)

    def on_change(self, request, obj, what):
        log_action(request, f"{self.audit_prefix}.{what}", obj, {"employee": obj.employee.full_name, "reason": obj.reason})
        notify(obj.employee, *self.message(obj, what), self.link)


class BonusViewSet(_RewardViewSet):
    serializer_class = BonusSerializer
    model = Bonus
    audit_prefix = "bonus"
    perm_prefix = "bonuses"
    link = "/bonuses"

    def message(self, b, what):
        t = {"create": "Sizga bonus berildi", "update": "Bonus yangilandi", "cancel": "Bonus bekor qilindi"}[what]
        return t, f"{_fmt(b.amount)} — {b.reason}"


class DisciplineViewSet(_RewardViewSet):
    serializer_class = DisciplineSerializer
    model = DisciplinaryRecord
    audit_prefix = "discipline"
    perm_prefix = "discipline"
    link = "/warnings"

    def get_queryset(self):
        qs = super().get_queryset()
        k = self.request.query_params.get("kind")
        return qs.filter(kind=k) if k in DisciplinaryRecord.Kind.values else qs

    def message(self, r, what):
        kind = r.get_kind_display()
        t = {"create": f"Sizga {kind.lower()} berildi", "update": f"{kind} yangilandi", "cancel": f"{kind} bekor qilindi"}[what]
        body = r.reason + (f" — {_fmt(r.amount)}" if r.amount else "")
        return t, body

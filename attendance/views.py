from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.audit import log_action
from accounts.permissions import IsActiveEmployee, require, sees_all
from employees.models import EmployeeProfile

from . import face, services
from .models import Attendance, ClinicLocation, FaceProfile
from .serializers import AttendanceSerializer, ClinicLocationSerializer


class _SubmitView(APIView):
    action = None
    permission_classes = [IsActiveEmployee]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "attendance"

    def post(self, request):
        try:
            record = services.submit(
                request, request.user.profile, self.action, request.data, request.FILES.get("image")
            )
        except services.AttendanceError as exc:
            return Response({"detail": exc.message, "code": exc.code}, status=exc.status)
        return Response(AttendanceSerializer(record).data, status=status.HTTP_201_CREATED if self.action == "check_in" else status.HTTP_200_OK)


class CheckInView(_SubmitView):
    action = "check_in"


class CheckOutView(_SubmitView):
    action = "check_out"


class AttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """Xodim faqat o'z yozuvlarini ko'radi (boshqasiniki 404). Administrator hammasini va filtrlarni ishlatadi."""

    serializer_class = AttendanceSerializer
    permission_classes = [IsActiveEmployee]

    def get_queryset(self):
        me = self.request.user.profile
        qs = Attendance.objects.select_related("employee", "employee__department")
        if not sees_all(self.request, "attendance"):
            return qs.filter(employee=me)
        p = self.request.query_params
        if p.get("employee"):
            qs = qs.filter(employee_id=p["employee"])
        if p.get("search"):
            qs = qs.filter(employee__full_name__icontains=p["search"].strip())
        if p.get("department"):
            qs = qs.filter(employee__department_id=p["department"])
        if p.get("position"):
            qs = qs.filter(employee__position__icontains=p["position"])
        if p.get("status") in dict(Attendance.Status.choices):
            qs = qs.filter(status=p["status"])
        if p.get("date_from"):
            qs = qs.filter(date__gte=p["date_from"])
        if p.get("date_to"):
            qs = qs.filter(date__lte=p["date_to"])
        return qs

    def filter_queryset(self, queryset):
        # Xodim uchun ham sana oralig'i filtri ishlaydi (faqat o'z yozuvlari ichida).
        p = self.request.query_params
        if not sees_all(self.request, "attendance"):
            if p.get("date_from"):
                queryset = queryset.filter(date__gte=p["date_from"])
            if p.get("date_to"):
                queryset = queryset.filter(date__lte=p["date_to"])
        return queryset

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except (ValueError, TypeError):
            return Response({"detail": "Sana formati YYYY-MM-DD bo'lishi kerak."}, status=400)


class TodayView(APIView):
    """Xodim bosh sahifasi uchun: bugungi holat va tugmalar holati."""

    permission_classes = [IsActiveEmployee]

    def get(self, request):
        me = request.user.profile
        today = timezone.localdate()
        shift = services.shift_date_for(me.schedule, timezone.now())
        rec = Attendance.objects.filter(employee=me, date=shift).first()
        if rec is None or rec.check_in is None:
            rec = services.open_overnight_record(me, timezone.now()) or rec
        loc = ClinicLocation.objects.filter(is_active=True).order_by("id").first()
        enrolled = FaceProfile.objects.filter(employee=me, is_active=True).exists()
        return Response({
            "date": today,
            "record": AttendanceSerializer(rec).data if rec else None,
            "can_check_in": rec is None,
            "shift_date": rec.date if rec else shift,
            "can_check_out": bool(rec and rec.check_in and not rec.check_out),
            "location_configured": loc is not None,
            "radius_m": loc.radius_m if loc else None,
            "check_mode": loc.check_mode if loc else None,
            "face": {
                "available": face.is_available(),
                "enrolled": enrolled,
                "mode": loc.face_mode if loc else None,
                "will_verify": face.is_available() and enrolled,
            },
        })


class LocationView(APIView):
    """Klinika joylashuvi va radiusi (faqat administrator)."""

    permission_classes = [require("settings.manage")]

    def _current(self):
        return ClinicLocation.objects.order_by("id").first()

    def get(self, request):
        loc = self._current()
        return Response({
            "location": ClinicLocationSerializer(loc).data if loc else None,
            "face_runtime": face.runtime_status(),
        })

    def put(self, request):
        loc = self._current()
        ser = ClinicLocationSerializer(loc, data=request.data, partial=loc is not None)
        ser.is_valid(raise_exception=True)
        obj = ser.save()
        log_action(request, "clinic_location.update", obj, {
            "radius_m": obj.radius_m, "max_accuracy_m": obj.max_accuracy_m,
            "check_mode": obj.check_mode, "face_mode": obj.face_mode,
        })
        return Response({"location": ser.data, "face_runtime": face.runtime_status()})


class FaceEnrollView(APIView):
    """Xodim yuzini ro'yxatdan o'tkazish (faqat administrator). Rasm saqlanmaydi, faqat shifrlangan vektor."""

    permission_classes = [require("employees.manage")]
    parser_classes = [MultiPartParser, FormParser]

    def _employee(self, employee_id):
        return EmployeeProfile.objects.filter(pk=employee_id).first()

    def get(self, request, employee_id):
        emp = self._employee(employee_id)
        if emp is None:
            return Response({"detail": "Xodim topilmadi."}, status=404)
        fp = FaceProfile.objects.filter(employee=emp, is_active=True).first()
        return Response({"enrolled": bool(fp), "enrolled_at": fp.enrolled_at if fp else None, "face_runtime": face.runtime_status()})

    def post(self, request, employee_id):
        emp = self._employee(employee_id)
        if emp is None:
            return Response({"detail": "Xodim topilmadi."}, status=404)
        if not face.is_available():
            return Response(
                {"detail": "Yuz verifikatsiyasi sozlanmagan (kutubxona, FACE_ENCRYPTION_KEY yoki FACE_VERIFICATION_ENABLED). README ga qarang."},
                status=400,
            )
        image = request.FILES.get("image")
        if image is None:
            return Response({"detail": "Rasm yuborilmadi."}, status=400)
        try:
            vec = face.embedding_from_image(image)
            blob = face.encrypt_embedding(vec)
        except face.FaceError as exc:
            return Response({"detail": str(exc)}, status=400)
        FaceProfile.objects.update_or_create(
            employee=emp, defaults={"encrypted_embedding": blob, "enrolled_by": request.user.profile, "is_active": True},
        )
        log_action(request, "face.enroll", emp, {"employee": emp.full_name})
        return Response({"enrolled": True}, status=201)

    def delete(self, request, employee_id):
        emp = self._employee(employee_id)
        if emp is None:
            return Response({"detail": "Xodim topilmadi."}, status=404)
        FaceProfile.objects.filter(employee=emp).delete()
        log_action(request, "face.delete", emp, {"employee": emp.full_name})
        return Response(status=204)

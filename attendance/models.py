from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from employees.models import EmployeeProfile


class ClinicLocation(models.Model):
    """Klinika koordinatalari va ruxsat etilgan radius (administrator sozlaydi)."""

    name = models.CharField(max_length=100, default="Gold Med Clinic")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-90), MaxValueValidator(90)])
    longitude = models.DecimalField(max_digits=9, decimal_places=6, validators=[MinValueValidator(-180), MaxValueValidator(180)])
    radius_m = models.PositiveIntegerField("Ruxsat etilgan radius (metr)", default=100, validators=[MinValueValidator(10), MaxValueValidator(5000)])
    max_accuracy_m = models.PositiveIntegerField("Maks. GPS aniqligi xatosi (metr)", default=100)
    class FaceMode(models.TextChoices):
        STRICT = "strict", "Qat'iy: yuz tekshirilmasa davomat qabul qilinmaydi"
        LENIENT = "lenient", "Yumshoq: yuz tekshirib bo'lmasa ham qayd etiladi (\"tekshirilmagan\" deb belgilanadi)"

    class CheckMode(models.TextChoices):
        EITHER = "either", "Yuz YOKI joylashuv (bittasi yetarli)"
        BOTH = "both", "Yuz VA joylashuv (ikkalasi ham)"

    # Davomat qanday tasdiqlanadi. "either": yuz mos kelsa YOKI klinika radiusida bo'lsa qabul qilinadi.
    # "both": joylashuv shart, yuz ro'yxatdan o'tgan va tizim sozlangan bo'lsa yuz ham shart.
    check_mode = models.CharField(max_length=10, choices=CheckMode.choices, default=CheckMode.EITHER)
    # Faqat "both" rejimida: yuzni tekshirib bo'lmasa (kutubxona yo'q yoki xodim ro'yxatdan o'tmagan) nima qilinsin.
    face_mode = models.CharField(max_length=10, choices=FaceMode.choices, default=FaceMode.LENIENT)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Klinika joylashuvi"
        verbose_name_plural = "Klinika joylashuvlari"

    def __str__(self):
        return f"{self.name} ({self.radius_m} m)"


class FaceProfile(models.Model):
    """
    Yuz verifikatsiyasi uchun shablon (embedding). Rasm SAQLANMAYDI —
    faqat shifrlangan raqamli vektor saqlanadi.
    """

    employee = models.OneToOneField(EmployeeProfile, on_delete=models.CASCADE, related_name="face_profile")
    encrypted_embedding = models.BinaryField("Shifrlangan yuz vektori")
    model_name = models.CharField(max_length=50, default="face_recognition/dlib")
    enrolled_by = models.ForeignKey(
        EmployeeProfile, on_delete=models.SET_NULL, null=True, related_name="+", verbose_name="Ro'yxatdan o'tkazgan admin"
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Yuz profili"
        verbose_name_plural = "Yuz profillari"

    def __str__(self):
        return f"Yuz: {self.employee}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        ON_TIME = "on_time", "O'z vaqtida"
        LATE = "late", "Kechikdi"
        ABSENT = "absent", "Kelmadi"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="attendances")
    date = models.DateField(db_index=True)
    check_in = models.DateTimeField("Ishga kelish (server vaqti)", null=True, blank=True)
    check_out = models.DateTimeField("Ishdan ketish (server vaqti)", null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ON_TIME, db_index=True)
    late_minutes = models.PositiveIntegerField(default=0)

    # Jadval nusxasi (keyin jadval o'zgarsa ham tarix buzilmasin)
    schedule_start = models.TimeField(null=True, blank=True)
    schedule_end = models.TimeField(null=True, blank=True)

    # Tekshiruv natijalari — kirish
    in_location_ok = models.BooleanField("Kirish: klinika radiusida", default=False)
    in_face_verified = models.BooleanField(default=False)
    in_face_distance = models.FloatField(null=True, blank=True)
    in_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    in_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    in_distance_m = models.FloatField(null=True, blank=True)
    in_accuracy_m = models.FloatField(null=True, blank=True)

    # Tekshiruv natijalari — chiqish
    out_location_ok = models.BooleanField("Chiqish: klinika radiusida", default=False)
    out_face_verified = models.BooleanField(default=False)
    out_face_distance = models.FloatField(null=True, blank=True)
    out_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    out_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    out_distance_m = models.FloatField(null=True, blank=True)
    out_accuracy_m = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-date", "employee__full_name"]
        verbose_name = "Davomat"
        verbose_name_plural = "Davomat yozuvlari"
        constraints = [
            models.UniqueConstraint(fields=["employee", "date"], name="uniq_attendance_employee_date"),
            models.CheckConstraint(
                condition=models.Q(check_out__isnull=True) | models.Q(check_in__isnull=False),
                name="attendance_checkout_needs_checkin",
            ),
        ]
        indexes = [models.Index(fields=["date", "status"])]

    def __str__(self):
        return f"{self.employee} — {self.date}"


class FaceAttemptLog(models.Model):
    """Rad etilgan va muvaffaqiyatli urinishlar (rasm saqlanmaydi)."""

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="attendance_attempts")
    action = models.CharField(max_length=10, choices=[("check_in", "Kirish"), ("check_out", "Chiqish")])
    success = models.BooleanField()
    reason = models.CharField(max_length=200, blank=True)
    face_distance = models.FloatField(null=True, blank=True)
    distance_m = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Davomat urinishi"
        verbose_name_plural = "Davomat urinishlari"

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models


class Department(models.Model):
    name = models.CharField("Bo'lim nomi", max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Bo'lim"
        verbose_name_plural = "Bo'limlar"

    def __str__(self):
        return self.name


class WorkSchedule(models.Model):
    """Ish jadvali. Kechikish shu jadvaldagi boshlanish vaqti + imtiyoz bilan hisoblanadi."""

    name = models.CharField(max_length=100, unique=True)
    start_time = models.TimeField("Ish boshlanishi")
    end_time = models.TimeField("Ish tugashi")
    grace_minutes = models.PositiveSmallIntegerField("Kechikish imtiyozi (daqiqa)", default=10)
    # Hafta kunlari: 0=Dushanba ... 6=Yakshanba, vergul bilan, masalan "0,1,2,3,4,5"
    work_days = models.CharField(
        max_length=20,
        default="0,1,2,3,4,5",
        validators=[RegexValidator(r"^[0-6](,[0-6])*$", "Masalan: 0,1,2,3,4,5")],
    )

    class Meta:
        verbose_name = "Ish jadvali"
        verbose_name_plural = "Ish jadvallari"
        constraints = [
        ]

    @property
    def crosses_midnight(self):
        """
        Smena ertasi kuni tugaydi: tugash vaqti boshlanishdan kichik (tungi, 22:00–06:00) yoki unga teng
        (sutkalik, 08:00–08:00 — to'liq 24 soat).
        """
        return self.end_time <= self.start_time

    @property
    def is_24h(self):
        return self.end_time == self.start_time

    def work_day_list(self):
        return [int(x) for x in self.work_days.split(",") if x != ""]

    def __str__(self):
        return f"{self.name} ({self.start_time:%H:%M}-{self.end_time:%H:%M})"


class EmployeeProfile(models.Model):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        EMPLOYEE = "employee", "Xodim"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField("F.I.Sh.", max_length=150)
    phone = models.CharField(
        "Telefon", max_length=20, blank=True, validators=[RegexValidator(r"^\+?\d{9,15}$", "Telefon raqami noto'g'ri")]
    )
    position = models.CharField("Lavozim", max_length=100)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="employees", null=True, blank=True)
    schedule = models.ForeignKey(WorkSchedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="employees")
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE, db_index=True)
    # Qo'shimcha ruxsatlar kodlari (accounts/rbac.py). Administrator roli uchun bo'sh qoladi: u hamma narsaga ega.
    permissions = models.JSONField("Ruxsatlar", default=list, blank=True)
    is_active = models.BooleanField("Faol", default=True, db_index=True)
    hired_at = models.DateField("Ishga qabul sanasi", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        verbose_name = "Xodim"
        verbose_name_plural = "Xodimlar"
        indexes = [models.Index(fields=["department", "is_active"]), models.Index(fields=["full_name"])]

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN

    def effective_permissions(self):
        """Administrator uchun barcha ruxsatlar; boshqalar uchun belgilanganlari (`.manage` => `.view`)."""
        from accounts import rbac

        if self.is_admin:
            return list(rbac.ALL_CODES)
        return rbac.normalize(self.permissions)

    def can(self, code):
        """Faol xodim shu amalni bajara oladimi (administrator hamma narsaga)."""
        if not self.is_active:
            return False
        return self.is_admin or code in self.effective_permissions()

    def can_any(self, *codes):
        return any(self.can(c) for c in codes)

    def __str__(self):
        return self.full_name

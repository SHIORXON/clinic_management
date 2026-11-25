from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from employees.models import EmployeeProfile


class Bonus(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="bonuses")
    amount = models.DecimalField("Miqdor (UZS)", max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0"))])
    reason = models.CharField("Sabab", max_length=255)
    date = models.DateField(default=timezone.localdate, db_index=True)
    is_cancelled = models.BooleanField(default=False)
    created_by = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Bonus"
        verbose_name_plural = "Bonuslar"
        indexes = [models.Index(fields=["employee", "date"])]


class DisciplinaryRecord(models.Model):
    class Kind(models.TextChoices):
        WARNING = "warning", "Ogohlantirish"
        FINE = "fine", "Jarima"
        REPRIMAND = "reprimand", "Hayfsan"

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="disciplinary_records")
    kind = models.CharField(max_length=10, choices=Kind.choices, db_index=True)
    reason = models.CharField("Sabab", max_length=255)
    note = models.TextField("Izoh", blank=True)
    amount = models.DecimalField("Jarima miqdori (UZS)", max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0"))])
    date = models.DateField(default=timezone.localdate, db_index=True)
    is_cancelled = models.BooleanField(default=False)
    created_by = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Intizomiy yozuv"
        verbose_name_plural = "Intizomiy yozuvlar"
        indexes = [models.Index(fields=["employee", "date"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind="fine") | models.Q(amount=0), name="amount_only_for_fines"
            )
        ]

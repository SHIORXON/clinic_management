from django.db import models

from employees.models import EmployeeProfile


class AuditLog(models.Model):
    """Muhim amallar tarixi: kim, nima, qachon, qaysi IP dan."""

    actor = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_entries")
    action = models.CharField(max_length=60, db_index=True)  # masalan: employee.create, attendance.check_in
    target_type = models.CharField(max_length=60, blank=True)
    target_id = models.CharField(max_length=40, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Audit yozuvi"
        verbose_name_plural = "Audit jurnali"
        indexes = [models.Index(fields=["target_type", "target_id"])]

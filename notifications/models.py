from django.db import models

from employees.models import EmployeeProfile


class Notification(models.Model):
    recipient = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=150)
    body = models.TextField(blank=True)
    link = models.CharField(max_length=100, blank=True)  # frontend manzili, masalan "/tasks"
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Bildirishnoma"
        verbose_name_plural = "Bildirishnomalar"
        indexes = [models.Index(fields=["recipient", "is_read"])]

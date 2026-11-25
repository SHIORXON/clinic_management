from django.db import models
from django.utils import timezone

from employees.models import Department, EmployeeProfile


class Task(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        IN_PROGRESS = "in_progress", "Jarayonda"
        SUBMITTED = "submitted", "Topshirilgan"
        APPROVED = "approved", "Tasdiqlangan"
        REWORK = "rework", "Qayta ishlash kerak"
        OVERDUE = "overdue", "Muddati o'tgan"

    title = models.CharField("Mazmuni", max_length=255)
    description = models.TextField("Tavsif", blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    start_date = models.DateField("Boshlanish", default=timezone.localdate)
    due_date = models.DateField("Tugash muddati", db_index=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NEW, db_index=True)
    created_by = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, related_name="created_tasks")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Vazifa"
        verbose_name_plural = "Vazifalar"
        constraints = [models.CheckConstraint(condition=models.Q(due_date__gte=models.F("start_date")), name="task_due_after_start")]
        indexes = [models.Index(fields=["status", "due_date"])]

    @property
    def is_overdue(self):
        done = {self.Status.APPROVED, self.Status.SUBMITTED}
        return self.status not in done and self.due_date < timezone.localdate()

    def __str__(self):
        return self.title


class TaskAssignment(models.Model):
    """Vazifa — xodim bog'lanishi. Har bir xodimning holati alohida yuritiladi."""

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="assignments")
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE, related_name="task_assignments")
    status = models.CharField(max_length=15, choices=Task.Status.choices, default=Task.Status.NEW, db_index=True)
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Vazifa biriktirish"
        verbose_name_plural = "Vazifa biriktirishlar"
        constraints = [models.UniqueConstraint(fields=["task", "employee"], name="uniq_task_employee")]
        indexes = [models.Index(fields=["employee", "status"])]

    def __str__(self):
        return f"{self.task} → {self.employee}"


def submission_path(instance, filename):
    return f"task_files/{instance.assignment.task_id}/{instance.assignment.employee_id}/{filename}"


class TaskSubmission(models.Model):
    assignment = models.ForeignKey(TaskAssignment, on_delete=models.CASCADE, related_name="submissions")
    comment = models.TextField("Izoh", blank=True)
    file = models.FileField(upload_to=submission_path, null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(EmployeeProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField("Admin izohi", blank=True)
    approved = models.BooleanField(null=True, blank=True)  # None = ko'rib chiqilmagan

    class Meta:
        ordering = ["-submitted_at"]
        verbose_name = "Vazifa topshirig'i"
        verbose_name_plural = "Vazifa topshiriqlari"

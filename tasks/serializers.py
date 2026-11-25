import os

from django.utils import timezone
from rest_framework import serializers

from employees.models import Department, EmployeeProfile

from .models import Task, TaskAssignment, TaskSubmission

ALLOWED_EXT = {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg", ".txt", ".zip"}
MAX_FILE_BYTES = 10 * 1024 * 1024
OPEN_STATUSES = (Task.Status.NEW, Task.Status.IN_PROGRESS, Task.Status.REWORK)


def display_status(assignment, today=None):
    """Muddati o'tgan holat bazada saqlanmaydi: ochiq vazifa va muddat o'tgan bo'lsa hisoblab chiqariladi."""
    today = today or timezone.localdate()
    if assignment.status in OPEN_STATUSES and assignment.task.due_date < today:
        return Task.Status.OVERDUE
    return assignment.status


class SubmissionSerializer(serializers.ModelSerializer):
    reviewed_by_name = serializers.CharField(source="reviewed_by.full_name", read_only=True, default=None)
    file_name = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()

    class Meta:
        model = TaskSubmission
        fields = ["id", "comment", "has_file", "file_name", "submitted_at", "reviewed_by_name",
                  "reviewed_at", "review_comment", "approved"]
        read_only_fields = fields

    def get_has_file(self, obj):
        return bool(obj.file)

    def get_file_name(self, obj):
        return os.path.basename(obj.file.name) if obj.file else None


class AssignmentSerializer(serializers.ModelSerializer):
    task_id = serializers.IntegerField(source="task.id", read_only=True)
    title = serializers.CharField(source="task.title", read_only=True)
    description = serializers.CharField(source="task.description", read_only=True)
    department = serializers.CharField(source="task.department.name", read_only=True, default=None)
    start_date = serializers.DateField(source="task.start_date", read_only=True)
    due_date = serializers.DateField(source="task.due_date", read_only=True)
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    created_by_name = serializers.CharField(source="task.created_by.full_name", read_only=True, default=None)
    display_status = serializers.SerializerMethodField()
    status_label = serializers.SerializerMethodField()
    submissions = SubmissionSerializer(many=True, read_only=True)

    class Meta:
        model = TaskAssignment
        fields = ["id", "task_id", "title", "description", "department", "start_date", "due_date",
                  "employee", "employee_name", "created_by_name", "status", "display_status",
                  "status_label", "assigned_at", "submissions"]
        read_only_fields = fields

    def get_display_status(self, obj):
        return display_status(obj)

    def get_status_label(self, obj):
        return Task.Status(display_status(obj)).label


class TaskCreateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    start_date = serializers.DateField(required=False)
    due_date = serializers.DateField()
    assignees = serializers.PrimaryKeyRelatedField(
        queryset=EmployeeProfile.objects.filter(is_active=True), many=True, allow_empty=False
    )

    def validate_title(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Topshiriq mazmunini kiriting.")
        return v

    def validate(self, attrs):
        start = attrs.get("start_date") or timezone.localdate()
        attrs["start_date"] = start
        if attrs["due_date"] < start:
            raise serializers.ValidationError({"due_date": "Muddat boshlanish sanasidan oldin bo'lishi mumkin emas."})
        return attrs


class TaskUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    start_date = serializers.DateField(required=False)
    due_date = serializers.DateField(required=False)


def validate_upload(f):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in ALLOWED_EXT:
        raise serializers.ValidationError("Bu turdagi fayl qabul qilinmaydi. Ruxsat: " + ", ".join(sorted(ALLOWED_EXT)))
    if f.size > MAX_FILE_BYTES:
        raise serializers.ValidationError("Fayl hajmi 10 MB dan oshmasligi kerak.")
    return f

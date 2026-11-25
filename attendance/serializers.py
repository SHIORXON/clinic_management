from rest_framework import serializers

from .models import Attendance, ClinicLocation


class AttendanceSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    department = serializers.CharField(source="employee.department.name", read_only=True, default=None)
    position = serializers.CharField(source="employee.position", read_only=True)
    status_label = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id", "employee", "employee_name", "department", "position", "date",
            "check_in", "check_out", "status", "status_label", "late_minutes",
            "schedule_start", "schedule_end",
            "in_face_verified", "in_location_ok", "in_distance_m",
            "out_face_verified", "out_location_ok", "out_distance_m",
            "created_at",
        ]
        read_only_fields = fields


class ClinicLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicLocation
        fields = ["id", "name", "latitude", "longitude", "radius_m", "max_accuracy_m", "check_mode", "face_mode", "is_active"]
        read_only_fields = ["id"]

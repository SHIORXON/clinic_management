from django.contrib import admin

from .models import Attendance, ClinicLocation, FaceAttemptLog, FaceProfile


@admin.register(ClinicLocation)
class ClinicLocationAdmin(admin.ModelAdmin):
    list_display = ("name", "latitude", "longitude", "radius_m", "face_mode", "is_active")


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "check_in", "check_out", "status", "late_minutes")
    list_filter = ("status", "date")
    search_fields = ("employee__full_name",)


@admin.register(FaceProfile)
class FaceProfileAdmin(admin.ModelAdmin):
    list_display = ("employee", "enrolled_at", "is_active")
    exclude = ("encrypted_embedding",)  # shifrlangan vektor admin oynasida ko'rsatilmaydi


@admin.register(FaceAttemptLog)
class FaceAttemptLogAdmin(admin.ModelAdmin):
    list_display = ("employee", "action", "success", "reason", "created_at")
    list_filter = ("success", "action")

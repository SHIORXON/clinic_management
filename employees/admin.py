from django.contrib import admin

from .models import Department, EmployeeProfile, WorkSchedule


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "start_time", "end_time", "grace_minutes", "work_days")


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "position", "department", "role", "is_active")
    list_filter = ("role", "is_active", "department")
    search_fields = ("full_name", "user__username", "phone")

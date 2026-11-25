from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from accounts import rbac
from accounts.permissions import profile_of

from .models import Department, EmployeeProfile, WorkSchedule

User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "employee_count"]


class WorkScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkSchedule
        fields = ["id", "name", "start_time", "end_time", "grace_minutes", "work_days"]


class EmployeeSerializer(serializers.ModelSerializer):
    username = serializers.CharField(max_length=150, write_only=True)
    password =serializers.CharField(write_only=True, required=False, trim_whitespace=False)
    department_name = serializers.CharField(source="department.name", read_only=True, default=None)
    schedule_name = serializers.CharField(source="schedule.name", read_only=True, default=None)
    face_enrolled = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeProfile
        fields = [
            "id", "username", "password", "full_name", "phone", "position",
            "department", "department_name", "schedule", "schedule_name",
            "role", "permissions", "is_active", "hired_at", "face_enrolled", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    # Faqat tanlash ro'yxatlari uchun (employees.view ruxsati bo'lmaganlarga): shaxsiy ma'lumotlarsiz.
    MINIMAL_FIELDS = ("id", "full_name", "position", "department", "department_name", "is_active", "role")

    def _actor(self):
        req = self.context.get("request")
        return profile_of(req.user) if req is not None else None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["username"] = instance.user.username
        data["permissions"] = rbac.normalize(instance.permissions)
        actor = self._actor()
        if actor is not None and not actor.can("employees.view"):
            return {k: v for k, v in data.items() if k in self.MINIMAL_FIELDS}
        return data

    def validate_permissions(self, value):
        bad = rbac.unknown(value)
        if bad:
            raise serializers.ValidationError("Noma'lum ruxsat: " + ", ".join(map(str, bad)))
        return rbac.normalize(value)

    def get_face_enrolled(self, obj):
        fp = getattr(obj, "face_profile", None)
        return bool(fp and fp.is_active)

    # --- validatsiya ---
    def validate_username(self, value):
        value = value.strip()
        qs = User.objects.filter(username__iexact=value)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.user_id)
        if qs.exists():
            raise serializers.ValidationError("Bu login band.")
        return value

    def validate(self, attrs):
        actor = self._actor()
        current_role = self.instance.role if self.instance else EmployeeProfile.Role.EMPLOYEE
        role = attrs.get("role", current_role)
        if actor is not None and not actor.is_admin:
            # Rol va ruxsatlarni faqat administrator belgilaydi (huquqni oshirib yuborishning oldini olish).
            if role != current_role:
                raise serializers.ValidationError({"role": "Rolni faqat administrator belgilaydi."})
            if "permissions" in attrs:
                current = rbac.normalize(self.instance.permissions) if self.instance else []
                if attrs["permissions"] != current:
                    raise serializers.ValidationError({"permissions": "Ruxsatlarni faqat administrator belgilaydi."})
        if role == EmployeeProfile.Role.ADMIN:
            attrs["permissions"] = []  # administrator hamma narsaga ega
        password = attrs.get("password")
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Yangi xodim uchun parol majburiy."})
        if password:
            try:
                validate_password(password)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": list(e.messages)})
        return attrs

    # --- yozish ---
    @transaction.atomic
    def create(self, validated):
        username = validated.pop("username")
        password = validated.pop("password")
        user = User.objects.create_user(
            username=username, password=password, is_active=validated.get("is_active", True)
        )
        return EmployeeProfile.objects.create(user=user, **validated)

    @transaction.atomic
    def update(self, instance, validated):
        user = instance.user
        username = validated.pop("username", None)
        password = validated.pop("password", None)
        if username:
            user.username = username
        if password:
            user.set_password(password)
        if "is_active" in validated:
            user.is_active = validated["is_active"]
        user.save()
        for attr, value in validated.items():
            setattr(instance, attr, value)
        instance.save()
        return instance

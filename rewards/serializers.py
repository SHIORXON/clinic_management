from decimal import Decimal

from rest_framework import serializers

from employees.models import EmployeeProfile

from .models import Bonus, DisciplinaryRecord


class _Base(serializers.ModelSerializer):
    employee = serializers.PrimaryKeyRelatedField(queryset=EmployeeProfile.objects.filter(is_active=True))
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    department = serializers.CharField(source="employee.department.name", read_only=True, default=None)
    created_by_name = serializers.CharField(source="created_by.full_name", read_only=True, default=None)

    def validate_reason(self, v):
        v = v.strip()
        if not v:
            raise serializers.ValidationError("Sababni kiriting.")
        return v

    def validate_employee(self, v):
        # Tahrirda xodimni almashtirish mumkin emas (tarix buzilmasligi uchun)
        if self.instance is not None and v.pk != self.instance.employee_id:
            raise serializers.ValidationError("Yozuv egasini o'zgartirib bo'lmaydi.")
        return v


class BonusSerializer(_Base):
    class Meta:
        model = Bonus
        fields = ["id", "employee", "employee_name", "department", "amount", "reason", "date",
                  "is_cancelled", "created_by_name", "created_at"]
        read_only_fields = ["id", "is_cancelled", "created_at"]

    def validate_amount(self, v):
        if v <= Decimal("0"):
            raise serializers.ValidationError("Miqdor noldan katta bo'lishi kerak.")
        return v


class DisciplineSerializer(_Base):
    kind_label = serializers.CharField(source="get_kind_display", read_only=True)

    class Meta:
        model = DisciplinaryRecord
        fields = ["id", "employee", "employee_name", "department", "kind", "kind_label", "reason", "note",
                  "amount", "date", "is_cancelled", "created_by_name", "created_at"]
        read_only_fields = ["id", "is_cancelled", "created_at"]

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", None))
        amount = attrs.get("amount", getattr(self.instance, "amount", Decimal("0")))
        if kind == DisciplinaryRecord.Kind.FINE:
            if amount <= 0:
                raise serializers.ValidationError({"amount": "Jarima miqdorini kiriting."})
        else:
            attrs["amount"] = Decimal("0")
        return attrs

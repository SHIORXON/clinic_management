from rest_framework.permissions import BasePermission


def profile_of(user):
    """Foydalanuvchining xodim profili (yo'q bo'lsa None)."""
    if not user or not user.is_authenticated:
        return None
    return getattr(user, "profile", None)


class IsActiveEmployee(BasePermission):
    """Tizimga kirgan va profili faol bo'lgan istalgan foydalanuvchi."""

    message = "Profilingiz faol emas yoki mavjud emas."

    def has_permission(self, request, view):
        p = profile_of(request.user)
        return bool(p and p.is_active)


class IsAdminRole(BasePermission):
    """Faqat faol administrator."""

    message = "Bu amal faqat administrator uchun."

    def has_permission(self, request, view):
        p = profile_of(request.user)
        return bool(p and p.is_active and p.is_admin)


def require(*codes):
    """
    Ruxsat klassi yasaydi: foydalanuvchida ko'rsatilgan ruxsatlardan KAMIDA BIRI bo'lishi kerak
    (administrator hammasiga ega). Masalan: `permission_classes = [require("reports.view")]`.
    """

    class HasPermission(BasePermission):
        message = "Bu amal uchun sizda ruxsat yo'q."

        def has_permission(self, request, view):
            p = profile_of(request.user)
            return bool(p and p.can_any(*codes))

    HasPermission.__name__ = "Require_" + "_".join(c.replace(".", "_") for c in codes)
    return HasPermission


def sees_all(request, prefix):
    """
    Barcha xodimlar ma'lumotini ko'rishi kerakmi. Administrator — har doim. Boshqalar — `<prefix>.view`
    ruxsati bo'lsa va so'rovda `?scope=all` berilgan bo'lsa (aks holda faqat o'z ma'lumoti).
    """
    p = profile_of(request.user)
    if not p or not p.is_active:
        return False
    if p.is_admin:
        return True
    return request.query_params.get("scope") == "all" and p.can(f"{prefix}.view")


class IsOwnerOrAdmin(BasePermission):
    """
    Obyekt darajasidagi himoya. Obyektda `employee` (EmployeeProfile) maydoni bo'lishi kerak.
    Xodim faqat o'ziga tegishli obyektni ko'ra oladi; administrator hammasini.
    """

    def has_object_permission(self, request, view, obj):
        p = profile_of(request.user)
        if not (p and p.is_active):
            return False
        if p.is_admin:
            return True
        return getattr(obj, "employee_id", None) == p.id

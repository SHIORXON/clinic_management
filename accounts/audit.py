from .models import AuditLog
from .permissions import profile_of


def client_ip(request):
    # Reverse-proxy ortida ishlatilsa, proxy X-Forwarded-For ni to'g'ri qo'yishi shart.
    if request is None:
        return None
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip() or None
    return request.META.get("REMOTE_ADDR") or None


def log_action(request, action, target=None, details=None, actor=None):
    """Muhim amalni audit jurnaliga yozadi. Parol va maxfiy maydonlarni details ga bermang."""
    if actor is None and request is not None:
        actor = profile_of(getattr(request, "user", None))
    AuditLog.objects.create(
        actor=actor,
        action=action,
        target_type=target.__class__.__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        details=details or {},
        ip_address=client_ip(request),
    )

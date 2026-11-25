from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from . import rbac
from .audit import log_action
from .permissions import IsActiveEmployee, profile_of, require


def me_payload(user):
    p = user.profile
    return {
        "id": p.id,
        "username": user.username,
        "full_name": p.full_name,
        "phone": p.phone,
        "position": p.position,
        "department": p.department.name if p.department_id else None,
        "role": p.role,
        "is_admin": p.is_admin,
        "permissions": p.effective_permissions(),
    }


class CsrfView(APIView):
    """Frontend sahifa ochilganda CSRF cookie olishi uchun."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # login o'zi sessiya yaratadi
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        # Login CSRF hujumiga qarshi: autentifikatsiyasiz so'rovda ham token tekshiriladi.
        SessionAuthentication().enforce_csrf(request)

        username = str(request.data.get("username", "")).strip()
        password = request.data.get("password", "")
        if not username or not password:
            return Response({"detail": "Login va parolni kiriting."}, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(request, username=username, password=password)
        fail = Response({"detail": "Login yoki parol noto'g'ri."}, status=status.HTTP_401_UNAUTHORIZED)
        if user is None:
            log_action(request, "auth.login_failed", details={"username": username[:150]})
            return fail

        p = profile_of(user)
        if p is None or not p.is_active:
            log_action(request, "auth.login_denied", details={"username": username[:150]})
            return Response(
                {"detail": "Hisobingiz faol emas. Administrator bilan bog'laning."}, status=status.HTTP_403_FORBIDDEN
            )

        login(request, user)  # sessiya kalitini yangilaydi (session fixation himoyasi)
        log_action(request, "auth.login", actor=p)
        return Response(me_payload(user))


class LogoutView(APIView):
    permission_classes = [IsActiveEmployee]

    def post(self, request):
        log_action(request, "auth.logout")
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsActiveEmployee]

    def get(self, request):
        return Response(me_payload(request.user))


class PermissionCatalogView(APIView):
    """Ruxsatlar ro'yxati va tayyor rol shablonlari (xodim formasi uchun). Ko'rish: xodim qo'sha oladiganlarga."""

    permission_classes = [require("employees.manage")]

    def get(self, request):
        return Response(rbac.catalog())


class ChangePasswordView(APIView):
    permission_classes = [IsActiveEmployee]

    def post(self, request):
        old = request.data.get("old_password", "")
        new = request.data.get("new_password", "")
        if not request.user.check_password(old):
            return Response({"old_password": ["Joriy parol noto'g'ri."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, user=request.user)
        except DjangoValidationError as e:
            return Response({"new_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        request.user.set_password(new)
        request.user.save(update_fields=["password"])
        update_session_auth_hash(request, request.user)  # joriy sessiya saqlanadi, boshqalari bekor bo'ladi
        log_action(request, "auth.password_changed")
        return Response({"detail": "Parol yangilandi."})

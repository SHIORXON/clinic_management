from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.permissions import IsActiveEmployee

from .models import Notification
from .serializers import NotificationSerializer


class NotificationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Foydalanuvchi faqat o'z bildirishnomalarini ko'radi."""

    serializer_class = NotificationSerializer
    permission_classes = [IsActiveEmployee]

    def get_queryset(self):
        qs = Notification.objects.filter(recipient=self.request.user.profile)
        if self.request.query_params.get("unread") in ("1", "true"):
            qs = qs.filter(is_read=False)
        return qs

    def list(self, request, *args, **kwargs):
        resp = super().list(request, *args, **kwargs)
        resp.data["unread"] = Notification.objects.filter(recipient=request.user.profile, is_read=False).count()
        return resp

    @action(detail=True, methods=["post"], url_path="read")
    def read(self, request, pk=None):
        n = self.get_object()  # boshqa foydalanuvchiniki -> 404
        if not n.is_read:
            n.is_read = True
            n.save(update_fields=["is_read"])
        return Response(self.get_serializer(n).data)

    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        n = Notification.objects.filter(recipient=request.user.profile, is_read=False).update(is_read=True)
        return Response({"updated": n})

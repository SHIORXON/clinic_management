from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import EmployeeProfile


@receiver(post_save, sender=get_user_model())
def create_admin_profile_for_superuser(sender, instance, created, **kwargs):
    """`createsuperuser` bilan yaratilgan foydalanuvchi avtomatik administrator profilini oladi."""
    if created and instance.is_superuser and not hasattr(instance, "profile"):
        EmployeeProfile.objects.create(
            user=instance,
            full_name=instance.get_full_name() or instance.username,
            position="Administrator",
            role=EmployeeProfile.Role.ADMIN,
        )

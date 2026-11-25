from employees.models import EmployeeProfile

from .models import Notification


def notify(recipients, title, body="", link=""):
    """Bir yoki bir nechta xodimga bildirishnoma yuboradi (faol bo'lmaganlarga yuborilmaydi)."""
    if isinstance(recipients, EmployeeProfile):
        recipients = [recipients]
    items = [
        Notification(recipient=r, title=title[:150], body=body, link=link)
        for r in {r.pk: r for r in recipients if r and r.is_active}.values()
    ]
    if items:
        Notification.objects.bulk_create(items)


def notify_admins(title, body="", link="", exclude=None):
    qs = EmployeeProfile.objects.filter(role=EmployeeProfile.Role.ADMIN, is_active=True)
    if exclude is not None:
        qs = qs.exclude(pk=exclude.pk)
    notify(list(qs), title, body, link)


def notify_managers(code, title, body="", link="", exclude=None):
    """Administratorlarga va `code` ruxsati bor faol xodimlarga bildirishnoma yuboradi."""
    people = [
        p for p in EmployeeProfile.objects.filter(is_active=True)
        if p.can(code) and (exclude is None or p.pk != exclude.pk)
    ]
    notify(people, title, body, link)

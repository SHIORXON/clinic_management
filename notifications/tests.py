from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from employees.models import EmployeeProfile

from .models import Notification
from .services import notify

User = get_user_model()
PW = "Str0ng-Pass-123"


def mk(username):
    u = User.objects.create_user(username=username, password=PW)
    return EmployeeProfile.objects.create(user=u, full_name=username.title(), position="Hamshira")


def cl(username):
    c = APIClient()
    assert c.login(username=username, password=PW)
    return c


class NotificationTests(APITestCase):
    def setUp(self):
        self.e1, self.e2 = mk("emp1"), mk("emp2")
        notify(self.e1, "A", "a")
        notify(self.e1, "B", "b")
        notify(self.e2, "C", "c")
        self.c1, self.c2 = cl("emp1"), cl("emp2")

    def test_list_own_with_unread(self):
        r = self.c1.get("/api/notifications/")
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(r.data["unread"], 2)

    def test_mark_read_and_isolation(self):
        n = Notification.objects.filter(recipient=self.e1).first()
        self.assertEqual(self.c2.post(f"/api/notifications/{n.id}/read/").status_code, 404)
        self.assertEqual(self.c1.post(f"/api/notifications/{n.id}/read/").status_code, 200)
        self.assertEqual(self.c1.get("/api/notifications/").data["unread"], 1)
        self.c1.post("/api/notifications/read-all/")
        self.assertEqual(self.c1.get("/api/notifications/").data["unread"], 0)
        self.assertEqual(self.c2.get("/api/notifications/").data["unread"], 1)  # boshqasiga ta'sir qilmaydi

    def test_anonymous_blocked(self):
        self.assertEqual(APIClient().get("/api/notifications/").status_code, 403)

    def test_inactive_not_notified(self):
        EmployeeProfile.objects.filter(pk=self.e2.pk).update(is_active=False)
        self.e2.refresh_from_db()
        notify(self.e2, "X")
        self.assertEqual(Notification.objects.filter(recipient=self.e2, title="X").count(), 0)

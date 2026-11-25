from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from accounts.models import AuditLog
from employees.models import EmployeeProfile
from notifications.models import Notification

from .models import Bonus, DisciplinaryRecord

User = get_user_model()
PW = "Str0ng-Pass-123"


def mk(username, role="employee"):
    u = User.objects.create_user(username=username, password=PW)
    return EmployeeProfile.objects.create(user=u, full_name=username.title(), position="Hamshira", role=role)


def cl(username):
    c = APIClient()
    assert c.login(username=username, password=PW)
    return c


class RewardTests(APITestCase):
    def setUp(self):
        self.admin, self.e1, self.e2 = mk("admin1", "admin"), mk("emp1"), mk("emp2")
        self.a, self.c1, self.c2 = cl("admin1"), cl("emp1"), cl("emp2")

    def test_bonus_flow(self):
        r = self.a.post("/api/bonuses/", {"employee": self.e1.id, "amount": "500000", "reason": "Yaxshi ish"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        bid = r.data["id"]
        self.assertEqual(Bonus.objects.get(pk=bid).created_by, self.admin)
        self.assertTrue(Notification.objects.filter(recipient=self.e1, title="Sizga bonus berildi").exists())
        self.assertTrue(AuditLog.objects.filter(action="bonus.create").exists())
        r = self.a.patch(f"/api/bonuses/{bid}/", {"amount": "600000"}, format="json")
        self.assertEqual(Bonus.objects.get(pk=bid).updated_by, self.admin)
        self.assertEqual(self.a.delete(f"/api/bonuses/{bid}/").status_code, 405)
        self.assertEqual(self.c1.get("/api/bonuses/").data["count"], 1)
        self.assertEqual(self.c2.get("/api/bonuses/").data["count"], 0)
        self.assertEqual(self.c2.get(f"/api/bonuses/{bid}/").status_code, 404)
        self.assertEqual(self.a.post(f"/api/bonuses/{bid}/cancel/").status_code, 200)
        self.assertEqual(self.c1.get("/api/bonuses/").data["count"], 0)  # bekor qilingan ko'rinmaydi
        self.assertEqual(self.a.get("/api/bonuses/").data["count"], 0)
        self.assertEqual(self.a.get("/api/bonuses/?cancelled=1").data["count"], 1)
        self.assertEqual(self.a.patch(f"/api/bonuses/{bid}/?cancelled=1", {"amount": "1"}, format="json").status_code, 400)

    def test_employee_cannot_write(self):
        p = {"employee": self.e1.id, "amount": "1000", "reason": "x"}
        self.assertEqual(self.c1.post("/api/bonuses/", p, format="json").status_code, 403)
        self.assertEqual(self.c1.post("/api/discipline/", {"employee": self.e1.id, "kind": "warning", "reason": "x"}, format="json").status_code, 403)
        b = Bonus.objects.create(employee=self.e1, amount=10, reason="r", created_by=self.admin)
        self.assertEqual(self.c1.patch(f"/api/bonuses/{b.id}/", {"amount": "99"}, format="json").status_code, 403)
        self.assertEqual(self.c1.post(f"/api/bonuses/{b.id}/cancel/").status_code, 403)

    def test_bonus_validation(self):
        for amount in ("0", "-5", "abc"):
            r = self.a.post("/api/bonuses/", {"employee": self.e1.id, "amount": amount, "reason": "x"}, format="json")
            self.assertEqual(r.status_code, 400, amount)
        self.assertEqual(self.a.post("/api/bonuses/", {"employee": self.e1.id, "amount": "10", "reason": " "}, format="json").status_code, 400)

    def test_discipline_rules(self):
        r = self.a.post("/api/discipline/", {"employee": self.e1.id, "kind": "fine", "reason": "Kechikish"}, format="json")
        self.assertEqual(r.status_code, 400)  # jarima summasiz bo'lmaydi
        r = self.a.post("/api/discipline/", {"employee": self.e1.id, "kind": "fine", "reason": "Kechikish", "amount": "50000"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        r = self.a.post("/api/discipline/", {"employee": self.e1.id, "kind": "warning", "reason": "Og'zaki", "amount": "999"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(float(r.data["amount"]), 0)  # ogohlantirishda summa nolga tushadi
        self.assertEqual(self.c1.get("/api/discipline/").data["count"], 2)
        self.assertEqual(self.c2.get("/api/discipline/").data["count"], 0)
        self.assertEqual(self.a.get("/api/discipline/?kind=fine").data["count"], 1)
        self.assertEqual(self.a.delete(f"/api/discipline/{r.data['id']}/").status_code, 405)
        self.assertTrue(Notification.objects.filter(recipient=self.e1, title__icontains="Sizga jarima").exists())

    def test_change_owner_blocked(self):
        b = Bonus.objects.create(employee=self.e1, amount=10, reason="r", created_by=self.admin)
        self.assertEqual(self.a.patch(f"/api/bonuses/{b.id}/", {"employee": self.e2.id}, format="json").status_code, 400)

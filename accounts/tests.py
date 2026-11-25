from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from employees.models import EmployeeProfile

from . import rbac

User = get_user_model()
PW = "Str0ng-Pass-123"


def mk(username, role="employee", perms=None):
    u = User.objects.create_user(username=username, password=PW)
    return EmployeeProfile.objects.create(
        user=u, full_name=username.title(), position="Lavozim", role=role, permissions=perms or []
    )


def cl(username):
    c = APIClient()
    assert c.login(username=username, password=PW)
    return c


class RbacUnitTests(APITestCase):
    def test_normalize(self):
        self.assertEqual(rbac.normalize(["tasks.manage", "zzz"]), ["tasks.view", "tasks.manage"])
        self.assertEqual(rbac.unknown(["tasks.view", "zzz"]), ["zzz"])

    def test_effective(self):
        self.assertEqual(set(mk("a1", "admin").effective_permissions()), set(rbac.ALL_CODES))
        self.assertEqual(mk("e1").effective_permissions(), [])
        self.assertTrue(mk("e2", perms=["bonuses.manage"]).can("bonuses.view"))


class RbacApiTests(APITestCase):
    def setUp(self):
        self.admin = mk("admin1", "admin")
        self.emp = mk("emp1")
        self.hr = mk("hr1", perms=["employees.manage"])
        self.rep = mk("rep1", perms=["reports.view", "dashboard.view"])
        self.a, self.e, self.h, self.r = cl("admin1"), cl("emp1"), cl("hr1"), cl("rep1")

    def test_me_has_permissions(self):
        self.assertEqual(self.e.get("/api/auth/me/").data["permissions"], [])
        self.assertIn("settings.manage", self.a.get("/api/auth/me/").data["permissions"])
        self.assertEqual(self.h.get("/api/auth/me/").data["permissions"], ["employees.view", "employees.manage"])

    def test_catalog_only_for_employee_managers(self):
        self.assertEqual(self.e.get("/api/auth/permissions/").status_code, 403)
        self.assertEqual(self.h.get("/api/auth/permissions/").status_code, 200)

    def test_admin_sets_permissions_on_create_and_update(self):
        r = self.a.post("/api/employees/", {
            "username": "new1", "password": PW, "full_name": "Yangi", "position": "Hamshira",
            "role": "employee", "permissions": ["tasks.manage", "reports.view"],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["permissions"], ["tasks.view", "tasks.manage", "reports.view"])
        r = self.a.patch(f"/api/employees/{r.data['id']}/", {"permissions": ["bonuses.view"]}, format="json")
        self.assertEqual(r.data["permissions"], ["bonuses.view"])

    def test_unknown_permission_rejected(self):
        r = self.a.patch(f"/api/employees/{self.emp.id}/", {"permissions": ["hack.all"]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_admin_role_clears_permissions(self):
        r = self.a.patch(f"/api/employees/{self.emp.id}/", {"role": "admin", "permissions": ["tasks.view"]}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["permissions"], [])

    def test_manager_cannot_grant_role_or_permissions(self):
        r = self.h.patch(f"/api/employees/{self.emp.id}/", {"role": "admin"}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.h.patch(f"/api/employees/{self.emp.id}/", {"permissions": ["settings.manage"]}, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.h.post("/api/employees/", {
            "username": "x1", "password": PW, "full_name": "X", "position": "P", "permissions": ["employees.manage"],
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_manager_cannot_touch_admin_or_self_or_higher(self):
        self.assertEqual(self.h.patch(f"/api/employees/{self.admin.id}/", {"position": "x"}, format="json").status_code, 403)
        self.assertEqual(self.h.patch(f"/api/employees/{self.hr.id}/", {"position": "x"}, format="json").status_code, 403)
        self.assertEqual(self.h.patch(f"/api/employees/{self.rep.id}/", {"position": "x"}, format="json").status_code, 403)  # rep1 ruxsatlari hr1 da yo'q
        self.assertEqual(self.h.patch(f"/api/employees/{self.emp.id}/", {"position": "Hamshira 2"}, format="json").status_code, 200)
        self.assertEqual(self.h.delete(f"/api/employees/{self.emp.id}/?permanent=true").status_code, 403)

    def test_employee_list_visibility(self):
        self.assertEqual(self.e.get("/api/employees/").status_code, 403)
        self.assertEqual(self.h.get("/api/employees/").status_code, 200)
        # hisobot ko'ra oladigan xodim tanlash uchun faqat qisqa ma'lumot oladi
        data = self.r.get("/api/employees/").data
        rows = data["results"] if isinstance(data, dict) else data
        self.assertNotIn("phone", rows[0])
        self.assertIn("full_name", rows[0])
        self.assertEqual(self.r.post("/api/employees/", {}, format="json").status_code, 403)

    def test_reports_and_dashboard(self):
        self.assertEqual(self.e.get("/api/reports/dashboard/").status_code, 403)
        self.assertEqual(self.r.get("/api/reports/dashboard/").status_code, 200)

    def test_settings_manage_gate(self):
        self.assertEqual(self.h.post("/api/departments/", {"name": "Yangi"}, format="json").status_code, 403)
        s = mk("set1", perms=["settings.manage"])
        self.assertEqual(cl("set1").post("/api/departments/", {"name": "Yangi"}, format="json").status_code, 201)
        self.assertIsNotNone(s)


class ScopeTests(APITestCase):
    def setUp(self):
        self.admin = mk("admin1", "admin")
        self.boss = mk("boss1", perms=["tasks.manage", "bonuses.manage", "attendance.view"])
        self.emp = mk("emp1")
        self.b, self.e = cl("boss1"), cl("emp1")
        self.due = str(timezone.localdate() + timedelta(days=3))

    def test_tasks_scope(self):
        r = self.b.post("/api/tasks/", {"title": "T", "due_date": self.due, "assignees": [self.emp.id]}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.b.get("/api/tasks/").data["count"], 0)  # o'zinikini ko'radi
        self.assertEqual(self.b.get("/api/tasks/?scope=all").data["count"], 1)
        self.assertEqual(self.e.get("/api/tasks/?scope=all").data["count"], 1)  # o'ziniki (ruxsatsiz scope e'tiborsiz)
        # tasks.manage bo'lmagan xodim yaratolmaydi
        self.assertEqual(self.e.post("/api/tasks/", {"title": "T", "due_date": self.due, "assignees": [self.emp.id]}, format="json").status_code, 403)

    def test_bonus_scope_and_manage(self):
        r = self.b.post("/api/bonuses/", {"employee": self.emp.id, "amount": 1000, "reason": "Yaxshi", "date": str(timezone.localdate())}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.b.get("/api/bonuses/").data["count"], 0)
        self.assertEqual(self.b.get("/api/bonuses/?scope=all").data["count"], 1)
        self.assertEqual(self.b.get("/api/discipline/?scope=all").data["count"], 0)
        # intizom ruxsati yo'q
        r = self.b.post("/api/discipline/", {"employee": self.emp.id, "kind": "warning", "reason": "x", "date": str(timezone.localdate())}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_attendance_scope(self):
        self.assertEqual(self.b.get("/api/attendance/").status_code, 200)
        self.assertEqual(self.b.get("/api/attendance/?scope=all").status_code, 200)
        self.assertEqual(self.b.get("/api/attendance/?scope=all&employee=%d" % self.emp.id).data["count"], 0)

    def test_summary_tasks_to_review(self):
        self.assertIn("tasks_to_review", self.b.get("/api/reports/summary/").data)
        self.assertNotIn("tasks_to_review", self.e.get("/api/reports/summary/").data)

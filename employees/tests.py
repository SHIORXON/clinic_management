from django.contrib.auth import get_user_model
from rest_framework.test import APIClient, APITestCase

from accounts.models import AuditLog

from .models import Department, EmployeeProfile

User = get_user_model()
PW = "Str0ng-Pass-123"


def make_user(username, role="employee", full_name=None, department=None, active=True):
    user = User.objects.create_user(username=username, password=PW, is_active=active)
    return EmployeeProfile.objects.create(
        user=user, full_name=full_name or username.title(), position="Hamshira",
        role=role, department=department, is_active=active,
    )


def client_for(username):
    c = APIClient()
    assert c.login(username=username, password=PW)
    return c


class AuthTests(APITestCase):
    def setUp(self):
        self.admin = make_user("admin1", role="admin")
        self.emp = make_user("nigora")

    def test_admin_can_login(self):
        r = self.client.post("/api/auth/login/", {"username": "admin1", "password": PW}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["is_admin"])

    def test_employee_can_login(self):
        r = self.client.post("/api/auth/login/", {"username": "nigora", "password": PW}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["role"], "employee")

    def test_wrong_password_rejected_and_audited(self):
        r = self.client.post("/api/auth/login/", {"username": "nigora", "password": "xato"}, format="json")
        self.assertEqual(r.status_code, 401)
        self.assertTrue(AuditLog.objects.filter(action="auth.login_failed").exists())

    def test_inactive_profile_cannot_login(self):
        make_user("ketgan", active=False)
        r = self.client.post("/api/auth/login/", {"username": "ketgan", "password": PW}, format="json")
        self.assertIn(r.status_code, (401, 403))

    def test_login_requires_csrf_when_enforced(self):
        c = APIClient(enforce_csrf_checks=True)
        r = c.post("/api/auth/login/", {"username": "nigora", "password": PW}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_me_requires_login(self):
        self.assertIn(self.client.get("/api/auth/me/").status_code, (401, 403))

    def test_logout_ends_session(self):
        c = client_for("nigora")
        self.assertEqual(c.get("/api/auth/me/").status_code, 200)
        self.assertEqual(c.post("/api/auth/logout/").status_code, 204)
        self.assertIn(c.get("/api/auth/me/").status_code, (401, 403))

    def test_change_password(self):
        c = client_for("nigora")
        bad = c.post("/api/auth/change-password/", {"old_password": "yoq", "new_password": "Yangi-Pass-456"}, format="json")
        self.assertEqual(bad.status_code, 400)
        weak = c.post("/api/auth/change-password/", {"old_password": PW, "new_password": "123"}, format="json")
        self.assertEqual(weak.status_code, 400)
        ok = c.post("/api/auth/change-password/", {"old_password": PW, "new_password": "Yangi-Pass-456"}, format="json")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(c.get("/api/auth/me/").status_code, 200)

    def test_superuser_gets_admin_profile(self):
        su = User.objects.create_superuser("root", password=PW)
        self.assertTrue(su.profile.is_admin)


class EmployeeAccessTests(APITestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Qabulxona")
        self.admin = make_user("admin1", role="admin")
        self.a = make_user("nigora", department=self.dept)
        self.b = make_user("sardor")

    def test_employee_cannot_list_or_read_other_employees(self):
        c = client_for("nigora")
        self.assertEqual(c.get("/api/employees/").status_code, 403)
        self.assertEqual(c.get(f"/api/employees/{self.b.id}/").status_code, 403)

    def test_employee_cannot_modify(self):
        c = client_for("nigora")
        self.assertEqual(c.post("/api/employees/", {}, format="json").status_code, 403)
        self.assertEqual(c.patch(f"/api/employees/{self.a.id}/", {"role": "admin"}, format="json").status_code, 403)
        self.assertEqual(c.delete(f"/api/employees/{self.b.id}/").status_code, 403)

    def test_anonymous_denied(self):
        self.assertIn(self.client.get("/api/employees/").status_code, (401, 403))

    def test_employee_can_read_but_not_write_departments(self):
        c = client_for("nigora")
        self.assertEqual(c.get("/api/departments/").status_code, 200)
        self.assertEqual(c.post("/api/departments/", {"name": "Yangi"}, format="json").status_code, 403)
        self.assertEqual(c.get("/api/schedules/").status_code, 403)


class EmployeeAdminTests(APITestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="Laboratoriya")
        self.dept2 = Department.objects.create(name="Xo'jalik")
        self.admin = make_user("admin1", role="admin")
        self.c = client_for("admin1")
        make_user("dilshod", full_name="Dilshod B.", department=self.dept)
        make_user("nigora", full_name="Nigora T.", department=self.dept2)

    def payload(self, **kw):
        base = {
            "username": "surayyo", "password": PW, "full_name": "Surayyo A.", "phone": "+998901234567",
            "position": "Buxgalter", "department": self.dept.id, "role": "employee", "is_active": True,
        }
        base.update(kw)
        return base

    def test_create_employee_saved_and_can_login(self):
        r = self.c.post("/api/employees/", self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertNotIn("password", r.json())
        e = EmployeeProfile.objects.get(user__username="surayyo")
        self.assertEqual(e.department_id, self.dept.id)
        self.assertNotEqual(e.user.password, PW)  # ochiq matnda emas
        self.assertTrue(e.user.check_password(PW))
        self.assertTrue(AuditLog.objects.filter(action="employee.create", target_id=str(e.pk)).exists())
        self.assertEqual(APIClient().post("/api/auth/login/", {"username": "surayyo", "password": PW}, format="json").status_code, 200)

    def test_create_requires_password_and_unique_username(self):
        p = self.payload()
        del p["password"]
        self.assertEqual(self.c.post("/api/employees/", p, format="json").status_code, 400)
        self.assertEqual(self.c.post("/api/employees/", self.payload(username="NIGORA"), format="json").status_code, 400)
        self.assertEqual(self.c.post("/api/employees/", self.payload(password="123"), format="json").status_code, 400)

    def test_invalid_phone_rejected(self):
        self.assertEqual(self.c.post("/api/employees/", self.payload(phone="abc"), format="json").status_code, 400)

    def test_search_and_filters(self):
        def names(q):
            return {x["full_name"] for x in self.c.get("/api/employees/" + q).json()["results"]}
        self.assertEqual(names("?search=dilshod"), {"Dilshod B."})
        self.assertEqual(names(f"?department={self.dept2.id}"), {"Nigora T."})
        self.assertEqual(names("?search=laboratoriya"), {"Dilshod B."})
        self.assertIn("Nigora T.", names("?is_active=true"))
        self.assertEqual(names("?is_active=false"), set())

    def test_update_changes_password_and_audits_without_leaking_it(self):
        e = EmployeeProfile.objects.get(user__username="nigora")
        r = self.c.patch(f"/api/employees/{e.id}/", {"position": "Katta hamshira", "password": "Yangi-Pass-456"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        e.refresh_from_db()
        self.assertEqual(e.position, "Katta hamshira")
        self.assertTrue(e.user.check_password("Yangi-Pass-456"))
        log = AuditLog.objects.filter(action="employee.update", target_id=str(e.pk)).latest("created_at")
        self.assertNotIn("Yangi-Pass-456", str(log.details))
        self.assertTrue(log.details["password_changed"])

    def test_deactivate_blocks_login_and_keeps_record(self):
        e = EmployeeProfile.objects.get(user__username="nigora")
        self.assertEqual(self.c.delete(f"/api/employees/{e.id}/").status_code, 204)
        e.refresh_from_db()
        self.assertFalse(e.is_active)
        self.assertFalse(e.user.is_active)
        r = APIClient().post("/api/auth/login/", {"username": "nigora", "password": PW}, format="json")
        self.assertIn(r.status_code, (401, 403))

    def test_permanent_delete(self):
        e = EmployeeProfile.objects.get(user__username="nigora")
        self.assertEqual(self.c.delete(f"/api/employees/{e.id}/?permanent=true").status_code, 204)
        self.assertFalse(User.objects.filter(username="nigora").exists())
        self.assertTrue(AuditLog.objects.filter(action="employee.delete").exists())

    def test_admin_cannot_lock_self_out(self):
        self.assertEqual(self.c.delete(f"/api/employees/{self.admin.id}/").status_code, 400)
        self.assertEqual(self.c.patch(f"/api/employees/{self.admin.id}/", {"is_active": False}, format="json").status_code, 400)
        self.assertEqual(self.c.patch(f"/api/employees/{self.admin.id}/", {"role": "employee"}, format="json").status_code, 400)

    def test_department_with_employees_cannot_be_deleted(self):
        self.assertEqual(self.c.delete(f"/api/departments/{self.dept.id}/").status_code, 400)
        empty = Department.objects.create(name="Bo'sh")
        self.assertEqual(self.c.delete(f"/api/departments/{empty.id}/").status_code, 204)

    def test_schedule_validation_and_assignment(self):
        full = self.c.post("/api/schedules/", {"name": "Sutkalik", "start_time": "09:00", "end_time": "09:00", "grace_minutes": 10, "work_days": "0,1,2"}, format="json")
        self.assertEqual(full.status_code, 201, full.content)  # teng vaqt = sutkalik (24 soat) smena
        night = self.c.post("/api/schedules/", {"name": "Tungi", "start_time": "22:00", "end_time": "06:00", "grace_minutes": 10, "work_days": "0,1,2"}, format="json")
        self.assertEqual(night.status_code, 201, night.content)  # tungi smena ruxsat etiladi
        badday = self.c.post("/api/schedules/", {"name": "X", "start_time": "09:00", "end_time": "18:00", "grace_minutes": 10, "work_days": "9"}, format="json")
        self.assertEqual(badday.status_code, 400)
        ok = self.c.post("/api/schedules/", {"name": "Kunduzgi", "start_time": "09:00", "end_time": "18:00", "grace_minutes": 10, "work_days": "0,1,2,3,4,5"}, format="json")
        self.assertEqual(ok.status_code, 201, ok.content)
        e = EmployeeProfile.objects.get(user__username="nigora")
        r = self.c.patch(f"/api/employees/{e.id}/", {"schedule": ok.json()["id"]}, format="json")
        self.assertEqual(r.json()["schedule_name"], "Kunduzgi")

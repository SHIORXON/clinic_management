import json

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.audit import log_action
from attendance.models import Attendance
from employees.models import Department, EmployeeProfile, WorkSchedule

User = get_user_model()
PW = "Str0ng-Pass-123"


def make_emp(username, role="employee", schedule=None, active=True):
    user = User.objects.create_user(username=username, password=PW)
    return EmployeeProfile.objects.create(
        user=user, full_name=username.title(), position="Hamshira", role=role, schedule=schedule, is_active=active
    )


def login(username):
    c = APIClient()
    assert c.login(username=username, password=PW)
    return c


class DashboardTests(APITestCase):
    def setUp(self):
        # Har kuni ish kuni bo'lgan jadval: testlar haftaning qaysi kuni ishga tushsa ham bir xil natija beradi
        self.sched = WorkSchedule.objects.create(name="Har kuni", start_time="00:00", end_time="18:00", grace_minutes=0, work_days="0,1,2,3,4,5,6")
        self.admin = make_emp("admin1", role="admin")
        self.a = make_emp("a", schedule=self.sched)
        self.b = make_emp("b", schedule=self.sched)
        self.c = make_emp("c", schedule=self.sched)
        make_emp("nojadval")  # jadvalsiz: "kelmagan" hisobiga kirmaydi
        make_emp("ketgan", schedule=self.sched, active=False)  # faolsiz: hisobga olinmaydi
        today = timezone.localdate()
        now = timezone.now()
        Attendance.objects.create(employee=self.a, date=today, check_in=now, status="on_time")
        Attendance.objects.create(employee=self.b, date=today, check_in=now, status="late", late_minutes=30)

    def test_numbers_come_from_database(self):
        r = login("admin1").get("/api/reports/dashboard/")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["total_employees"], 5)  # admin + a + b + c + nojadval
        self.assertEqual(d["expected_today"], 3)
        self.assertEqual(d["present_today"], 2)
        self.assertEqual(d["late_today"], 1)
        self.assertEqual(d["absent_today"], 1)
        self.assertEqual(len(d["weekly"]), 6)
        today_idx = timezone.localdate().weekday()
        if today_idx < 6:
            self.assertEqual(d["weekly"][today_idx]["kelgan"], 2)
            self.assertEqual(d["weekly"][today_idx]["vaqtida"], 1)

    def test_employee_and_anonymous_denied(self):
        self.assertEqual(login("a").get("/api/reports/dashboard/").status_code, 403)
        self.assertIn(APIClient().get("/api/reports/dashboard/").status_code, (401, 403))

    def test_activity_log_readable_and_hides_noise(self):
        log_action(None, "employee.create", details={"full_name": "Yangi Xodim"}, actor=self.admin)
        log_action(None, "auth.login_failed", details={"username": "kimdir"}, actor=None)
        log_action(None, "attendance.check_in", actor=self.a)
        d = login("admin1").get("/api/reports/dashboard/").json()
        texts = [f"{x['who']} {x['what']}" for x in d["activity"]]
        self.assertIn("Admin1 yangi xodim qo'shdi: Yangi Xodim", texts)
        self.assertIn("A ishga kelganini qayd etdi", texts)
        self.assertFalse(any("kimdir" in t for t in texts))


class IndexAndSeedTests(APITestCase):
    def test_index_for_anonymous_has_no_user_data(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('id="boot-data"', html)
        self.assertIn("null", html.split('id="boot-data"')[1].split("</script>")[0])
        self.assertIn("csrftoken", r.cookies)  # frontend X-CSRFToken uchun
        self.assertIn("dist/app.js", html)

    def test_index_for_logged_in_user_embeds_only_own_profile(self):
        make_emp("nigora")
        c = login("nigora")
        html = c.get("/").content.decode()
        data = json.loads(html.split('id="boot-data" type="application/json">')[1].split("</script>")[0])
        self.assertEqual(data["username"], "nigora")
        self.assertFalse(data["is_admin"])

    def test_inactive_profile_gets_login_screen(self):
        e = make_emp("ketgan")
        c = login("ketgan")
        e.is_active = False
        e.save()
        html = c.get("/").content.decode()
        self.assertIn("null", html.split('id="boot-data"')[1].split("</script>")[0])

    def test_seed_initial_is_idempotent_and_creates_no_people(self):
        call_command("seed_initial", verbosity=0)
        call_command("seed_initial", verbosity=0)
        self.assertEqual(Department.objects.count(), 6)
        self.assertEqual(WorkSchedule.objects.count(), 5)
        self.assertEqual(EmployeeProfile.objects.count(), 0)


class ReportsTests(APITestCase):
    def setUp(self):
        from datetime import timedelta
        from decimal import Decimal

        from rewards.models import Bonus, DisciplinaryRecord
        from tasks.models import Task, TaskAssignment

        sched = WorkSchedule.objects.create(name="S", start_time="09:00", end_time="18:00", work_days="0,1,2,3,4,5,6")
        self.admin = make_emp("rep_admin", "admin")
        self.e1 = make_emp("rep_e1")
        self.e1.schedule = sched
        self.e1.save()
        self.e2 = make_emp("rep_e2")
        self.today = timezone.localdate()
        # e1 tizimda 10 kun oldin yaratilgan deb hisoblaymiz
        EmployeeProfile.objects.filter(pk=self.e1.pk).update(created_at=timezone.now() - timedelta(days=10))
        y = self.today - timedelta(days=1)
        Attendance.objects.create(employee=self.e1, date=y, check_in=timezone.now(), status="late", late_minutes=12)
        Bonus.objects.create(employee=self.e1, amount=Decimal("100000"), reason="Zo'r", created_by=self.admin, date=y)
        Bonus.objects.create(employee=self.e1, amount=Decimal("5000"), reason="Bekor", created_by=self.admin, date=y, is_cancelled=True)
        DisciplinaryRecord.objects.create(employee=self.e1, kind="fine", amount=Decimal("20000"), reason="Kechikish", created_by=self.admin, date=y)
        t = Task.objects.create(title="=SUM(A1)", start_date=y - timedelta(days=3), due_date=y, created_by=self.admin)
        TaskAssignment.objects.create(task=t, employee=self.e1)
        self.a = login("rep_admin")
        self.c = login("rep_e1")
        self.q = f"date_from={self.today - timedelta(days=3)}&date_to={self.today}"

    def test_employee_forbidden_everywhere(self):
        for k in ("attendance", "tasks", "bonuses", "discipline"):
            self.assertEqual(self.c.get(f"/api/reports/{k}/").status_code, 403)
            self.assertEqual(self.c.get(f"/api/reports/{k}/?export=xlsx").status_code, 403)
        self.assertEqual(self.c.get("/api/reports/dashboard/").status_code, 403)

    def test_attendance_includes_computed_absent(self):
        r = self.a.get(f"/api/reports/attendance/?{self.q}")
        self.assertEqual(r.status_code, 200)
        s = r.data["summary"]
        self.assertEqual(s["Kechikkan"], 1)
        self.assertEqual(s["Kelmagan"], 2)  # e1: 3 kunning 2 tasi (bugun hisoblanmaydi) — kecha kelgan
        self.assertEqual(self.a.get(f"/api/reports/attendance/?{self.q}&status=absent").data["count"], 2)
        self.assertEqual(self.a.get(f"/api/reports/attendance/?{self.q}&employee={self.e2.id}").data["count"], 0)

    def test_bonus_excludes_cancelled_and_tasks_overdue(self):
        r = self.a.get(f"/api/reports/bonuses/?{self.q}")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(r.data["summary"]["Jami summa (so'm)"], "100 000")
        r = self.a.get(f"/api/reports/tasks/?{self.q}&status=overdue")
        self.assertEqual(r.data["count"], 1)
        self.assertEqual(self.a.get(f"/api/reports/discipline/?{self.q}").data["count"], 1)

    def test_bad_filters(self):
        self.assertEqual(self.a.get("/api/reports/attendance/?date_from=abc").status_code, 400)
        self.assertEqual(self.a.get("/api/reports/attendance/?date_from=2025-01-01&date_to=2025-12-31").status_code, 400)
        self.assertEqual(self.a.get("/api/reports/attendance/?date_from=2025-02-01&date_to=2025-01-01").status_code, 400)
        self.assertEqual(self.a.get("/api/reports/nope/").status_code, 404)
        self.assertEqual(self.a.get("/api/reports/bonuses/?export=docx").status_code, 400)

    def test_exports_are_valid_files(self):
        import io

        from openpyxl import load_workbook

        for k in ("attendance", "tasks", "bonuses", "discipline"):
            r = self.a.get(f"/api/reports/{k}/?{self.q}&export=xlsx")
            self.assertEqual(r.status_code, 200)
            wb = load_workbook(io.BytesIO(r.content))
            self.assertGreaterEqual(wb.active.max_row, 5)
            p = self.a.get(f"/api/reports/{k}/?{self.q}&export=pdf")
            self.assertEqual(p.status_code, 200)
            self.assertTrue(p.content.startswith(b"%PDF"))
        # formula inyeksiyasi neytrallashgan
        wb = load_workbook(io.BytesIO(self.a.get(f"/api/reports/tasks/?{self.q}&export=xlsx").content))
        vals = [c.value for row in wb.active.iter_rows(min_row=5) for c in row if c.value]
        self.assertNotIn("=SUM(A1)", vals)
        self.assertIn("'=SUM(A1)", vals)

    def test_dashboard_extension_and_summary(self):
        d = self.a.get("/api/reports/dashboard/").data
        for k in ("tasks_in_progress", "tasks_overdue", "bonus_sum_month", "discipline_count_month", "tasks_weekly"):
            self.assertIn(k, d)
        self.assertEqual(d["tasks_overdue"], 1)
        s = self.c.get("/api/reports/summary/").data
        self.assertEqual(s["overdue_tasks"], 1)
        self.assertEqual(s["open_tasks"], 1)
        self.assertIn("tasks_to_review", self.a.get("/api/reports/summary/").data)


class PwaTests(APITestCase):
    def test_manifest_sw_offline(self):
        r = self.client.get("/manifest.webmanifest")
        self.assertEqual(r.status_code, 200)
        m = json.loads(r.content)
        self.assertEqual(m["display"], "standalone")
        self.assertTrue(any(i["purpose"] == "maskable" for i in m["icons"]))
        sw = self.client.get("/sw.js")
        self.assertEqual(sw.status_code, 200)
        self.assertEqual(sw["Service-Worker-Allowed"], "/")
        self.assertEqual(self.client.get("/offline/").status_code, 200)

    def test_static_assets_exist(self):
        from django.conf import settings
        for f in ("dist/app.js", "dist/app.css", "vendor/react.min.js", "vendor/recharts.min.js", "pwa/icon-512.png"):
            self.assertTrue((settings.BASE_DIR / "static" / f).exists(), f)

    def test_assetlinks(self):
        from django.test import override_settings
        self.assertEqual(json.loads(self.client.get("/.well-known/assetlinks.json").content), [])
        with override_settings(ANDROID_PACKAGE_NAME="uz.goldmed.app", ANDROID_SHA256_FINGERPRINTS=["AA:BB"]):
            d = json.loads(self.client.get("/.well-known/assetlinks.json").content)
        self.assertEqual(d[0]["target"]["package_name"], "uz.goldmed.app")
        self.assertEqual(d[0]["target"]["sha256_cert_fingerprints"], ["AA:BB"])

    def test_index_has_no_external_scripts(self):
        html = self.client.get("/").content.decode()
        self.assertNotIn("unpkg.com", html)
        self.assertNotIn("cdn.tailwindcss.com", html)
        self.assertNotIn("babel", html.lower())

    def test_privacy_page_public(self):
        r = self.client.get("/privacy/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Maxfiylik siyosati", r.content.decode())

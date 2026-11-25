import shutil
import tempfile
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from employees.models import EmployeeProfile
from notifications.models import Notification

from .models import Task, TaskAssignment

User = get_user_model()
PW = "Str0ng-Pass-123"
TMP = tempfile.mkdtemp()


def mk(username, role="employee"):
    u = User.objects.create_user(username=username, password=PW)
    return EmployeeProfile.objects.create(user=u, full_name=username.title(), position="Hamshira", role=role)


def cl(username):
    c = APIClient()
    assert c.login(username=username, password=PW)
    return c


@override_settings(MEDIA_ROOT=TMP)
class TaskFlowTests(APITestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def setUp(self):
        self.admin, self.e1, self.e2 = mk("admin1", "admin"), mk("emp1"), mk("emp2")
        self.a, self.c1, self.c2 = cl("admin1"), cl("emp1"), cl("emp2")
        today = timezone.localdate()
        self.payload = {"title": "Xonani tozalash", "due_date": str(today + timedelta(days=3)), "assignees": [self.e1.id, self.e2.id]}

    def create(self):
        r = self.a.post("/api/tasks/", self.payload, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    def test_admin_creates_for_many_and_notifies(self):
        data = self.create()
        self.assertEqual(len(data), 2)
        self.assertEqual(Notification.objects.filter(title="Yangi topshiriq").count(), 2)

    def test_employee_cannot_create_or_review_or_delete(self):
        self.assertEqual(self.c1.post("/api/tasks/", self.payload, format="json").status_code, 403)
        aid = self.create()[0]["id"]
        self.assertEqual(self.c1.post(f"/api/tasks/{aid}/review/", {"approved": True}, format="json").status_code, 403)
        self.assertEqual(self.c1.delete(f"/api/tasks/{aid}/").status_code, 403)
        self.assertEqual(self.c1.patch(f"/api/tasks/{aid}/", {"title": "x"}, format="json").status_code, 403)

    def test_validation(self):
        bad = {**self.payload, "due_date": str(timezone.localdate() - timedelta(days=1))}
        self.assertEqual(self.a.post("/api/tasks/", bad, format="json").status_code, 400)
        self.assertEqual(self.a.post("/api/tasks/", {**self.payload, "assignees": []}, format="json").status_code, 400)
        self.assertEqual(self.a.post("/api/tasks/", {**self.payload, "title": "  "}, format="json").status_code, 400)

    def test_employee_sees_only_own(self):
        data = self.create()
        mine = {x["employee"]: x["id"] for x in data}
        r = self.c1.get("/api/tasks/")
        self.assertEqual([x["employee"] for x in r.data["results"]], [self.e1.id])
        self.assertEqual(self.c1.get(f"/api/tasks/{mine[self.e2.id]}/").status_code, 404)
        self.assertEqual(self.c1.post(f"/api/tasks/{mine[self.e2.id]}/start/").status_code, 404)
        self.assertEqual(self.a.get("/api/tasks/").data["count"], 2)

    def test_full_cycle_with_rework(self):
        aid = {x["employee"]: x["id"] for x in self.create()}[self.e1.id]
        self.assertEqual(self.c1.post(f"/api/tasks/{aid}/start/").data["status"], "in_progress")
        # bo'sh topshirish
        self.assertEqual(self.c1.post(f"/api/tasks/{aid}/submit/", {}, format="multipart").status_code, 400)
        f = SimpleUploadedFile("hisobot.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        r = self.c1.post(f"/api/tasks/{aid}/submit/", {"comment": "Tayyor", "file": f}, format="multipart")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(r.data["status"], "submitted")
        sid = r.data["submissions"][0]["id"]
        self.assertTrue(Notification.objects.filter(recipient=self.admin, title="Topshiriq topshirildi").exists())
        # qayta topshirib bo'lmaydi
        self.assertEqual(self.c1.post(f"/api/tasks/{aid}/submit/", {"comment": "yana"}, format="multipart").status_code, 400)
        # qaytarish uchun sabab shart
        self.assertEqual(self.a.post(f"/api/tasks/{aid}/review/", {"approved": False}, format="json").status_code, 400)
        r = self.a.post(f"/api/tasks/{aid}/review/", {"approved": False, "comment": "Rasm yo'q"}, format="json")
        self.assertEqual(r.data["status"], "rework")
        self.assertTrue(Notification.objects.filter(recipient=self.e1, title__icontains="qayta ishlash").exists())
        # qayta topshirish va tasdiqlash
        self.c1.post(f"/api/tasks/{aid}/submit/", {"comment": "Tuzatdim"}, format="multipart")
        r = self.a.post(f"/api/tasks/{aid}/review/", {"approved": True}, format="json")
        self.assertEqual(r.data["status"], "approved")
        self.assertEqual(self.a.post(f"/api/tasks/{aid}/review/", {"approved": True}, format="json").status_code, 400)
        # fayl: egasi va admin yuklay oladi, boshqa xodim yo'q
        self.assertEqual(self.c1.get(f"/api/tasks/files/{sid}/").status_code, 200)
        self.assertEqual(self.a.get(f"/api/tasks/files/{sid}/").status_code, 200)
        self.assertEqual(self.c2.get(f"/api/tasks/files/{sid}/").status_code, 404)
        self.assertEqual(APIClient().get(f"/api/tasks/files/{sid}/").status_code, 403)

    def test_file_validation(self):
        aid = self.create()[0]["id"]
        asg = TaskAssignment.objects.get(pk=aid)
        c = cl(asg.employee.user.username)
        bad = SimpleUploadedFile("virus.exe", b"MZ", content_type="application/octet-stream")
        self.assertEqual(c.post(f"/api/tasks/{aid}/submit/", {"file": bad}, format="multipart").status_code, 400)
        big = SimpleUploadedFile("big.pdf", b"0" * (10 * 1024 * 1024 + 1), content_type="application/pdf")
        self.assertEqual(c.post(f"/api/tasks/{aid}/submit/", {"file": big}, format="multipart").status_code, 400)

    def test_overdue_is_computed(self):
        data = self.create()
        t = Task.objects.get()
        Task.objects.filter(pk=t.pk).update(start_date=timezone.localdate() - timedelta(days=5), due_date=timezone.localdate() - timedelta(days=1))
        r = self.c1.get("/api/tasks/")
        self.assertEqual(r.data["results"][0]["display_status"], "overdue")
        self.assertEqual(self.c1.get("/api/tasks/?status=overdue").data["count"], 1)
        self.assertEqual(self.c1.get("/api/tasks/?status=new").data["count"], 0)
        # muddati o'tgan bo'lsa ham topshirish mumkin
        aid = r.data["results"][0]["id"]
        self.assertEqual(self.c1.post(f"/api/tasks/{aid}/submit/", {"comment": "kech"}, format="multipart").status_code, 200)
        self.assertEqual(self.c1.get("/api/tasks/?status=overdue").data["count"], 0)

    def test_admin_edit_and_delete(self):
        aid = self.create()[0]["id"]
        r = self.a.patch(f"/api/tasks/{aid}/", {"title": "Yangi nom"}, format="json")
        self.assertEqual(r.data["title"], "Yangi nom")
        self.assertEqual(self.a.delete(f"/api/tasks/{aid}/").status_code, 204)
        self.assertEqual(Task.objects.count(), 0)

    def test_anonymous_blocked(self):
        self.assertEqual(APIClient().get("/api/tasks/").status_code, 403)

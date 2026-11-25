from datetime import datetime
from unittest import mock

import numpy as np
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase

from accounts.models import AuditLog
from employees.models import Department, EmployeeProfile, WorkSchedule

from . import face
from .geo import haversine_m
from .models import Attendance, ClinicLocation, FaceAttemptLog, FaceProfile

User = get_user_model()
PW = "Str0ng-Pass-123"
CLINIC = (41.311081, 69.240562)
INSIDE = {"latitude": 41.3111, "longitude": 69.2406, "accuracy": 15}
OUTSIDE = {"latitude": 41.3200, "longitude": 69.2406, "accuracy": 15}  # ~1 km


def make_emp(username, role="employee", schedule=None):
    user = User.objects.create_user(username=username, password=PW)
    return EmployeeProfile.objects.create(
        user=user, full_name=username.title(), position="Hamshira", role=role, schedule=schedule
    )


def login(username):
    c = APIClient()
    assert c.login(username=username, password=PW)
    return c


def img():
    return SimpleUploadedFile("face.jpg", b"fake-image-bytes", content_type="image/jpeg")


def at(y, m, d, hh, mm):
    return timezone.make_aware(datetime(y, m, d, hh, mm))


class Base(APITestCase):
    def setUp(self):
        self.sched = WorkSchedule.objects.create(name="Kunduzgi", start_time="09:00", end_time="18:00", grace_minutes=10)
        self.admin = make_emp("admin1", role="admin")
        self.emp = make_emp("nigora", schedule=self.sched)
        self.other = make_emp("sardor", schedule=self.sched)
        self.loc = ClinicLocation.objects.create(
            latitude=CLINIC[0], longitude=CLINIC[1], radius_m=100, max_accuracy_m=100,
            check_mode="both",  # eski testlar "ikkalasi ham" qoidasini tekshiradi; "yoki" qoidasi alohida klassda
        )
        self.c = login("nigora")

    def check_in(self, data=None, client=None, **kw):
        return (client or self.c).post("/api/attendance/check-in/", INSIDE if data is None else data, format="multipart", **kw)

    def check_out(self, data=None, client=None):
        return (client or self.c).post("/api/attendance/check-out/", INSIDE if data is None else data, format="multipart")


class GeoTests(APITestCase):
    def test_haversine(self):
        self.assertAlmostEqual(haversine_m(*CLINIC, *CLINIC), 0, places=3)
        # 0.001 daraja kenglik ~ 111.2 m
        self.assertAlmostEqual(haversine_m(41.0, 69.0, 41.001, 69.0), 111.2, delta=0.5)


class CheckInOutTests(Base):
    def test_check_in_inside_radius_saved_with_server_time(self):
        r = self.check_in({**INSIDE, "timestamp": "2000-01-01T00:00:00Z", "check_in": "2000-01-01T00:00:00Z"})
        self.assertEqual(r.status_code, 201, r.content)
        rec = Attendance.objects.get(employee=self.emp)
        self.assertEqual(rec.check_in.year, timezone.now().year)  # mijoz vaqti hisobga olinmadi
        self.assertEqual(rec.date, timezone.localdate())
        self.assertLess(rec.in_distance_m, 100)
        self.assertFalse(rec.in_face_verified)  # yuz sozlanmagan: "tekshirilmagan"
        self.assertTrue(FaceAttemptLog.objects.filter(employee=self.emp, success=True).exists())
        self.assertTrue(AuditLog.objects.filter(action="attendance.check_in").exists())

    def test_outside_radius_rejected_and_nothing_saved(self):
        r = self.check_in(OUTSIDE)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "outside_radius")
        self.assertFalse(Attendance.objects.exists())
        log = FaceAttemptLog.objects.get()
        self.assertFalse(log.success)

    def test_admin_changes_radius(self):
        self.assertEqual(self.check_in(OUTSIDE).status_code, 403)
        self.loc.radius_m = 2000
        self.loc.save()
        self.assertEqual(self.check_in(OUTSIDE).status_code, 201)

    def test_low_gps_accuracy_rejected(self):
        r = self.check_in({**INSIDE, "accuracy": 500})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "low_accuracy")

    def test_bad_or_missing_coordinates_rejected(self):
        for bad in ({}, {**INSIDE, "latitude": "abc"}, {**INSIDE, "latitude": 999}, {**INSIDE, "longitude": "nan"}, {"latitude": 41.3, "longitude": 69.2}):
            r = self.check_in(bad)
            self.assertEqual(r.status_code, 400, bad)
        self.assertFalse(Attendance.objects.exists())

    def test_no_location_configured(self):
        ClinicLocation.objects.all().delete()
        self.assertEqual(self.check_in().status_code, 503)

    def test_anonymous_denied(self):
        self.assertIn(self.check_in(client=APIClient()).status_code, (401, 403))

    def test_double_check_in(self):
        self.assertEqual(self.check_in().status_code, 201)
        self.assertEqual(self.check_in().status_code, 409)
        self.assertEqual(Attendance.objects.count(), 1)

    def test_check_out_flow(self):
        self.assertEqual(self.check_out().status_code, 409)  # kirishsiz chiqish yo'q
        self.check_in()
        self.assertEqual(self.check_out(OUTSIDE).status_code, 403)  # chiqishda ham radius tekshiriladi
        r = self.check_out()
        self.assertEqual(r.status_code, 200, r.content)
        rec = Attendance.objects.get()
        self.assertIsNotNone(rec.check_out)
        self.assertGreaterEqual(rec.check_out, rec.check_in)
        self.assertEqual(self.check_out().status_code, 409)

    def test_late_status_from_schedule(self):
        # 2026-10-26 — dushanba (ish kuni); jadval 09:00, imtiyoz 10 daqiqa
        cases = [((9, 5), "on_time", 0), ((9, 10), "on_time", 0), ((9, 25), "late", 25)]
        for i, ((hh, mm), status, late) in enumerate(cases):
            emp = make_emp(f"xodim{i}", schedule=self.sched)
            with mock.patch("attendance.services.timezone.now", return_value=at(2026, 10, 26, hh, mm)):
                r = self.check_in(client=login(emp.user.username))
            self.assertEqual(r.status_code, 201, r.content)
            rec = Attendance.objects.get(employee=emp)
            self.assertEqual((rec.status, rec.late_minutes), (status, late))
            self.assertEqual(rec.schedule_start.hour, 9)

    def test_no_lateness_on_non_work_day_or_without_schedule(self):
        with mock.patch("attendance.services.timezone.now", return_value=at(2026, 10, 25, 12, 0)):  # yakshanba
            self.check_in()
        self.assertEqual(Attendance.objects.get(employee=self.emp).status, "on_time")
        with mock.patch("attendance.services.timezone.now", return_value=at(2026, 10, 26, 12, 0)):
            self.check_in(client=login("admin1"))  # jadvalsiz admin
        self.assertEqual(Attendance.objects.get(employee=self.admin).status, "on_time")

    def test_strict_mode_blocks_when_face_not_configured(self):
        self.loc.face_mode = "strict"
        self.loc.save()
        r = self.check_in()
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "face_not_configured")
        self.assertFalse(Attendance.objects.exists())


@override_settings(FACE_ENCRYPTION_KEY=Fernet.generate_key().decode(), FACE_VERIFICATION_ENABLED=True, FACE_MATCH_TOLERANCE=0.5)
class FaceTests(Base):
    KNOWN = np.zeros(128)

    def setUp(self):
        super().setUp()
        FaceProfile.objects.create(employee=self.emp, encrypted_embedding=face.encrypt_embedding(self.KNOWN))
        p1 = mock.patch("attendance.services.face.is_available", return_value=True)
        p1.start()
        self.addCleanup(p1.stop)

    def with_vec(self, vec):
        return mock.patch("attendance.services.face.embedding_from_image", return_value=vec)

    def test_matching_face_accepted_and_marked_verified(self):
        with self.with_vec(self.KNOWN + 0.01):
            r = self.client_post(INSIDE)
        self.assertEqual(r.status_code, 201, r.content)
        rec = Attendance.objects.get()
        self.assertTrue(rec.in_face_verified)
        self.assertIsNotNone(rec.in_face_distance)

    def client_post(self, data, with_image=True, url="/api/attendance/check-in/"):
        payload = {**data, **({"image": img()} if with_image else {})}
        return self.c.post(url, payload, format="multipart")

    def test_wrong_face_rejected_even_in_lenient_mode(self):
        with self.with_vec(np.ones(128) * 0.5):
            r = self.client_post(INSIDE)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "face_mismatch")
        self.assertFalse(Attendance.objects.exists())
        self.assertFalse(FaceAttemptLog.objects.get().success)

    def test_missing_image_rejected_when_face_enrolled(self):
        r = self.client_post(INSIDE, with_image=False)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "no_image")

    def test_no_face_in_photo_rejected(self):
        with mock.patch("attendance.services.face.embedding_from_image", side_effect=face.FaceError("Rasmda yuz topilmadi.")):
            r = self.client_post(INSIDE)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Attendance.objects.exists())

    def test_check_out_also_verifies_face(self):
        with self.with_vec(self.KNOWN):
            self.assertEqual(self.client_post(INSIDE).status_code, 201)
        with self.with_vec(np.ones(128)):
            self.assertEqual(self.client_post(INSIDE, url="/api/attendance/check-out/").status_code, 403)
        with self.with_vec(self.KNOWN):
            r = self.client_post(INSIDE, url="/api/attendance/check-out/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Attendance.objects.get().out_face_verified)

    def test_unenrolled_employee_strict_vs_lenient(self):
        c = login("sardor")  # yuzi ro'yxatdan o'tkazilmagan
        r = c.post("/api/attendance/check-in/", {**INSIDE, "image": img()}, format="multipart")
        self.assertEqual(r.status_code, 201)
        self.assertFalse(Attendance.objects.get(employee=self.other).in_face_verified)
        Attendance.objects.all().delete()
        self.loc.face_mode = "strict"
        self.loc.save()
        r = c.post("/api/attendance/check-in/", {**INSIDE, "image": img()}, format="multipart")
        self.assertEqual(r.status_code, 403)

    def test_embedding_is_encrypted_and_roundtrips(self):
        vec = np.random.rand(128)
        blob = face.encrypt_embedding(vec)
        self.assertNotIn(vec.tobytes(), blob)
        np.testing.assert_allclose(face.decrypt_embedding(blob), vec)
        with override_settings(FACE_ENCRYPTION_KEY=Fernet.generate_key().decode()):
            with self.assertRaises(face.FaceError):
                face.decrypt_embedding(blob)

    def test_enroll_endpoint_admin_only_and_stores_no_image(self):
        FaceProfile.objects.all().delete()
        url = f"/api/attendance/face/{self.emp.id}/"
        self.assertEqual(self.c.post(url, {"image": img()}, format="multipart").status_code, 403)
        admin = login("admin1")
        with self.with_vec(self.KNOWN):
            r = admin.post(url, {"image": img()}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        fp = FaceProfile.objects.get(employee=self.emp)
        np.testing.assert_allclose(face.decrypt_embedding(fp.encrypted_embedding), self.KNOWN)
        self.assertTrue(AuditLog.objects.filter(action="face.enroll").exists())
        self.assertEqual(admin.delete(url).status_code, 204)
        self.assertFalse(FaceProfile.objects.exists())

    def test_enroll_refused_when_face_unavailable(self):
        with mock.patch("attendance.services.face.is_available", return_value=False), \
                mock.patch("attendance.views.face.is_available", return_value=False):
            r = login("admin1").post(f"/api/attendance/face/{self.emp.id}/", {"image": img()}, format="multipart")
        self.assertEqual(r.status_code, 400)


class FaceUnavailableTests(Base):
    def test_default_environment_reports_not_available(self):
        # dlib o'rnatilmagan va yoqilmagan: tizim yuz tekshiruvini "ishlayapti" deb ko'rsatmasligi kerak
        self.assertFalse(face.is_available())
        r = self.c.get("/api/attendance/today/")
        self.assertFalse(r.json()["face"]["available"])
        self.assertFalse(r.json()["face"]["will_verify"])


class ReadAccessTests(Base):
    def setUp(self):
        super().setUp()
        self.check_in()
        self.other_client = login("sardor")
        self.check_in(client=self.other_client)

    def test_employee_sees_only_own_records(self):
        r = self.c.get("/api/attendance/")
        self.assertEqual(r.status_code, 200)
        ids = {x["employee"] for x in r.json()["results"]}
        self.assertEqual(ids, {self.emp.id})
        # ?employee= bilan ham boshqasini ko'ra olmaydi
        r = self.c.get(f"/api/attendance/?employee={self.other.id}")
        self.assertEqual(r.json()["results"][0]["employee"], self.emp.id)

    def test_employee_cannot_open_others_record(self):
        other_rec = Attendance.objects.get(employee=self.other)
        self.assertEqual(self.c.get(f"/api/attendance/{other_rec.id}/").status_code, 404)

    def test_employee_cannot_write_records(self):
        rec = Attendance.objects.get(employee=self.emp)
        self.assertEqual(self.c.patch(f"/api/attendance/{rec.id}/", {"status": "late"}, format="json").status_code, 405)
        self.assertEqual(self.c.delete(f"/api/attendance/{rec.id}/").status_code, 405)

    def test_admin_sees_all_and_filters(self):
        a = login("admin1")
        self.assertEqual(a.get("/api/attendance/").json()["count"], 2)
        self.assertEqual(a.get(f"/api/attendance/?employee={self.other.id}").json()["count"], 1)
        self.assertEqual(a.get("/api/attendance/?date_from=2999-01-01").json()["count"], 0)
        # holat tekshiruv vaqtiga bog'liq (09:10 dan keyin "late"), shuning uchun yig'indini tekshiramiz
        late = a.get("/api/attendance/?status=late").json()["count"]
        on_time = a.get("/api/attendance/?status=on_time").json()["count"]
        self.assertEqual(late + on_time, 2)
        self.assertEqual(a.get("/api/attendance/?status=absent").json()["count"], 0)

    def test_today_endpoint(self):
        r = self.c.get("/api/attendance/today/").json()
        self.assertFalse(r["can_check_in"])
        self.assertTrue(r["can_check_out"])
        self.assertEqual(r["radius_m"], 100)
        self.assertNotIn("latitude", str(r))  # klinika koordinatalari xodimga berilmaydi


class LocationSettingsTests(Base):
    def test_employee_cannot_read_or_change_location(self):
        self.assertEqual(self.c.get("/api/attendance/location/").status_code, 403)
        self.assertEqual(self.c.put("/api/attendance/location/", {"radius_m": 5000}, format="json").status_code, 403)

    def test_admin_updates_location_and_it_is_audited(self):
        a = login("admin1")
        r = a.put("/api/attendance/location/", {"latitude": "41.3", "longitude": "69.2", "radius_m": 250, "face_mode": "strict"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.loc.refresh_from_db()
        self.assertEqual((self.loc.radius_m, self.loc.face_mode), (250, "strict"))
        self.assertTrue(AuditLog.objects.filter(action="clinic_location.update").exists())
        self.assertIn("face_runtime", a.get("/api/attendance/location/").json())

    def test_invalid_values_rejected(self):
        a = login("admin1")
        for bad in ({"radius_m": 1}, {"radius_m": 999999}, {"latitude": "200"}, {"face_mode": "x"}):
            self.assertEqual(a.put("/api/attendance/location/", bad, format="json").status_code, 400, bad)

    def test_admin_can_create_first_location(self):
        ClinicLocation.objects.all().delete()
        r = login("admin1").put("/api/attendance/location/", {"name": "Gold Med", "latitude": "41.3", "longitude": "69.2", "radius_m": 100}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(ClinicLocation.objects.count(), 1)


@override_settings(FACE_ENCRYPTION_KEY=Fernet.generate_key().decode(), FACE_VERIFICATION_ENABLED=True, FACE_MATCH_TOLERANCE=0.5)
class EitherModeTests(Base):
    """check_mode="either": yuz mos kelsa YOKI joylashuv to'g'ri bo'lsa davomat qabul qilinadi."""

    KNOWN = np.zeros(128)
    GOOD = np.zeros(128) + 0.01
    BAD = np.ones(128) * 0.5

    def setUp(self):
        super().setUp()
        self.loc.check_mode = "either"
        self.loc.save()
        FaceProfile.objects.create(employee=self.emp, encrypted_embedding=face.encrypt_embedding(self.KNOWN))
        p = mock.patch("attendance.services.face.is_available", return_value=True)
        p.start()
        self.addCleanup(p.stop)

    def post(self, data, vec=None, url="/api/attendance/check-in/", client=None):
        payload = dict(data)
        if vec is not None:
            payload["image"] = img()
        with mock.patch("attendance.services.face.embedding_from_image", return_value=vec):
            return (client or self.c).post(url, payload, format="multipart")

    def test_default_mode_for_new_location_is_either(self):
        self.assertEqual(ClinicLocation._meta.get_field("check_mode").default, "either")

    def test_location_only_is_enough_without_face(self):
        r = self.post(INSIDE)  # rasm yuborilmadi
        self.assertEqual(r.status_code, 201, r.content)
        rec = Attendance.objects.get()
        self.assertTrue(rec.in_location_ok)
        self.assertFalse(rec.in_face_verified)

    def test_face_only_is_enough_outside_radius(self):
        r = self.post(OUTSIDE, vec=self.GOOD)
        self.assertEqual(r.status_code, 201, r.content)
        rec = Attendance.objects.get()
        self.assertTrue(rec.in_face_verified)
        self.assertFalse(rec.in_location_ok)  # administrator buni jadvalda ko'radi
        self.assertGreater(rec.in_distance_m, 100)

    def test_face_only_without_any_location_data(self):
        r = self.post({}, vec=self.GOOD)
        self.assertEqual(r.status_code, 201, r.content)
        rec = Attendance.objects.get()
        self.assertTrue(rec.in_face_verified)
        self.assertFalse(rec.in_location_ok)
        self.assertIsNone(rec.in_latitude)
        self.assertIsNone(rec.in_distance_m)

    def test_face_only_when_gps_accuracy_is_poor(self):
        r = self.post({**INSIDE, "accuracy": 500}, vec=self.GOOD)
        self.assertEqual(r.status_code, 201, r.content)
        rec = Attendance.objects.get()
        self.assertTrue(rec.in_face_verified)
        self.assertFalse(rec.in_location_ok)

    def test_wrong_face_but_inside_radius_passes_by_location(self):
        r = self.post(INSIDE, vec=self.BAD)
        self.assertEqual(r.status_code, 201, r.content)
        rec = Attendance.objects.get()
        self.assertTrue(rec.in_location_ok)
        self.assertFalse(rec.in_face_verified)
        self.assertIn("yuz tasdiqlanmadi", FaceAttemptLog.objects.get(success=True).reason)

    def test_wrong_face_and_outside_radius_rejected_with_both_reasons(self):
        r = self.post(OUTSIDE, vec=self.BAD)
        self.assertEqual(r.status_code, 403)
        msg = r.json()["detail"]
        self.assertIn("Yuz tasdiqlanmadi", msg)
        self.assertIn("hududidan tashqarida", msg)
        self.assertFalse(Attendance.objects.exists())

    def test_nothing_usable_is_rejected(self):
        r = self.post({})  # na joylashuv, na rasm
        self.assertEqual(r.status_code, 400)
        self.assertIn("Yuz rasmi yuborilmadi", r.json()["detail"])
        self.assertIn("Joylashuv yuborilmadi", r.json()["detail"])
        self.assertFalse(Attendance.objects.exists())

    def test_without_possible_face_only_location_path_exists(self):
        # sardor yuzi ro'yxatdan o'tmagan: faqat joylashuv yo'li bor
        c = login("sardor")
        r = self.post(OUTSIDE, vec=self.GOOD, client=c)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "outside_radius")
        self.assertEqual(self.post({}, client=c).json()["code"], "no_location_data")
        self.assertEqual(self.post(INSIDE, client=c).status_code, 201)

    def test_poor_accuracy_without_face_still_rejected(self):
        r = self.post({**INSIDE, "accuracy": 500})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()["code"], "low_accuracy")

    def test_check_out_either_mode(self):
        self.assertEqual(self.post(INSIDE).status_code, 201)
        r = self.post(OUTSIDE, vec=self.GOOD, url="/api/attendance/check-out/")
        self.assertEqual(r.status_code, 200, r.content)
        rec = Attendance.objects.get()
        self.assertTrue(rec.out_face_verified)
        self.assertFalse(rec.out_location_ok)

    def test_both_mode_still_requires_location_even_with_matching_face(self):
        self.loc.check_mode = "both"
        self.loc.save()
        r = self.post(OUTSIDE, vec=self.GOOD)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(r.json()["code"], "outside_radius")

    def test_api_exposes_location_flags_and_mode(self):
        self.post(OUTSIDE, vec=self.GOOD)
        row = self.c.get("/api/attendance/").json()["results"][0]
        self.assertTrue(row["in_face_verified"])
        self.assertFalse(row["in_location_ok"])
        self.assertEqual(self.c.get("/api/attendance/today/").json()["check_mode"], "either")

    def test_admin_can_switch_mode(self):
        a = login("admin1")
        r = a.put("/api/attendance/location/", {"check_mode": "both"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.loc.refresh_from_db()
        self.assertEqual(self.loc.check_mode, "both")
        self.assertEqual(a.put("/api/attendance/location/", {"check_mode": "x"}, format="json").status_code, 400)


class NightShiftTests(APITestCase):
    """Tungi smena 22:00–06:00: sana = smena boshlangan kun; chiqish ertasi kuni qayd etiladi."""

    def setUp(self):
        self.sched = WorkSchedule.objects.create(name="Tungi", start_time="22:00", end_time="06:00", grace_minutes=10, work_days="0,1,2,3,4")
        self.emp = make_emp("tungi", schedule=self.sched)
        ClinicLocation.objects.create(latitude=CLINIC[0], longitude=CLINIC[1], radius_m=100, max_accuracy_m=100, check_mode="either")
        self.c = login("tungi")

    def post(self, kind, when):
        with mock.patch("attendance.services.timezone.now", return_value=when):
            return self.c.post(f"/api/attendance/{kind}/", INSIDE, format="multipart")

    def today(self, when):
        with mock.patch("attendance.services.timezone.now", return_value=when):
            return self.c.get("/api/attendance/today/").data

    def test_check_in_evening_and_out_next_morning_is_one_record(self):
        mon = (2026, 10, 26)
        r = self.post("check-in", at(*mon, 21, 55))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["date"], "2026-10-26")
        self.assertEqual(r.data["status"], "on_time")
        # ertasi kuni 03:00 — hali kechagi smena, "chiqish" tugmasi faol
        t = self.today(at(2026, 10, 27, 3, 0))
        self.assertTrue(t["can_check_out"])
        self.assertFalse(t["can_check_in"])
        self.assertEqual(t["record"]["date"], "2026-10-26")
        r = self.post("check-out", at(2026, 10, 27, 6, 5))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(Attendance.objects.count(), 1)
        rec = Attendance.objects.get()
        self.assertEqual(str(rec.date), "2026-10-26")
        self.assertIsNotNone(rec.check_out)

    def test_late_for_night_shift_after_midnight(self):
        r = self.post("check-in", at(2026, 10, 27, 1, 0))  # smena 22:00 da boshlangan, 3 soat kechikish
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["date"], "2026-10-26")
        self.assertEqual(r.data["status"], "late")
        self.assertEqual(r.data["late_minutes"], 180)

    def test_double_check_in_blocked_across_midnight(self):
        self.post("check-in", at(2026, 10, 26, 22, 0))
        r = self.post("check-in", at(2026, 10, 27, 2, 0))
        self.assertEqual(r.status_code, 409)

    def test_new_shift_next_evening_after_checkout(self):
        self.post("check-in", at(2026, 10, 26, 22, 0))
        self.post("check-out", at(2026, 10, 27, 6, 0))
        r = self.post("check-in", at(2026, 10, 27, 21, 50))
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(Attendance.objects.count(), 2)

    def test_forgot_checkout_can_still_start_next_shift(self):
        self.post("check-in", at(2026, 10, 26, 22, 0))  # chiqish unutildi
        r = self.post("check-in", at(2026, 10, 27, 21, 55))
        self.assertEqual(r.status_code, 201, r.data)

    def test_checkout_without_checkin_rejected(self):
        self.assertEqual(self.post("check-out", at(2026, 10, 27, 5, 0)).status_code, 409)

    def test_non_workday_early_morning_belongs_to_that_day(self):
        # shanba 02:00: juma ish kuni bo'lsa ham shanba smenasi emas — juma smenasi (juma 4 = ish kuni)
        r = self.post("check-in", at(2026, 10, 31, 2, 0))
        self.assertEqual(r.data["date"], "2026-10-30")
        # yakshanba 02:00: shanba ish kuni emas -> yakshanba sanasi bilan yoziladi
        c2 = make_emp("tungi2", schedule=self.sched)
        cl = login("tungi2")
        with mock.patch("attendance.services.timezone.now", return_value=at(2026, 11, 1, 2, 0)):
            r = cl.post("/api/attendance/check-in/", INSIDE, format="multipart")
        self.assertEqual(r.data["date"], "2026-11-01")


class DayNightShiftVariantsTests(APITestCase):
    """Sutkalik (08:00–08:00) va ertalabki/kechki smenalar."""

    def setUp(self):
        ClinicLocation.objects.create(latitude=CLINIC[0], longitude=CLINIC[1], radius_m=100, max_accuracy_m=100, check_mode="either")

    def post(self, c, kind, when):
        with mock.patch("attendance.services.timezone.now", return_value=when):
            return c.post(f"/api/attendance/{kind}/", INSIDE, format="multipart")

    def test_24h_shift_cycle(self):
        s = WorkSchedule.objects.create(name="Sutkalik", start_time="08:00", end_time="08:00", grace_minutes=10, work_days="0,1,2,3,4,5,6")
        self.assertTrue(s.is_24h and s.crosses_midnight)
        make_emp("sutka", schedule=s)
        c = login("sutka")
        r = self.post(c, "check-in", at(2026, 10, 26, 8, 3))
        self.assertEqual((r.status_code, r.data["status"], r.data["date"]), (201, "on_time", "2026-10-26"))
        with mock.patch("attendance.services.timezone.now", return_value=at(2026, 10, 27, 3, 0)):
            t = c.get("/api/attendance/today/").data
        self.assertTrue(t["can_check_out"] and not t["can_check_in"])
        r = self.post(c, "check-out", at(2026, 10, 27, 8, 5))
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(str(Attendance.objects.get().date), "2026-10-26")
        # keyingi smenaga oldinroq kelish — yangi sana, 409 emas
        r = self.post(c, "check-in", at(2026, 10, 27, 7, 55))
        self.assertEqual((r.status_code, r.data["date"], r.data["status"]), (201, "2026-10-27", "on_time"))
        self.assertEqual(Attendance.objects.count(), 2)

    def test_evening_shift_not_overnight(self):
        s = WorkSchedule.objects.create(name="Kechki", start_time="15:00", end_time="23:00", grace_minutes=10, work_days="0,1,2,3,4,5")
        self.assertFalse(s.crosses_midnight)
        make_emp("kechki", schedule=s)
        c = login("kechki")
        r = self.post(c, "check-in", at(2026, 10, 26, 15, 30))
        self.assertEqual((r.data["status"], r.data["late_minutes"]), ("late", 30))
        self.assertEqual(self.post(c, "check-out", at(2026, 10, 26, 23, 1)).status_code, 200)

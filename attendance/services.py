"""
Davomat qoidalari. Barcha tekshiruvlar SERVERDA bajariladi; brauzerdan kelgan vaqt e'tiborga olinmaydi.

Ikki tekshiruv bor: joylashuv (GPS klinika radiusida va yetarli aniqlikda) va yuz (kamera rasmi
xodimning ro'yxatdan o'tgan yuziga mos). Qaysi biri yetarli ekanini klinika sozlamasi (`check_mode`) belgilaydi:

  either  — yuz mos kelsa YOKI joylashuv to'g'ri bo'lsa, davomat qabul qilinadi (bittasi yetarli).
  both    — joylashuv shart; yuz ro'yxatdan o'tgan va tizim sozlangan bo'lsa, yuz ham mos kelishi shart.
"""
import math
from datetime import datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.audit import log_action

from . import face
from .geo import haversine_m
from .models import Attendance, ClinicLocation, FaceAttemptLog, FaceProfile


class AttendanceError(Exception):
    def __init__(self, message, status=400, code="rejected"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def _number(value, label, lo, hi):
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise AttendanceError(f"{label} noto'g'ri yuborildi.", 400, "bad_coordinates")
    if not math.isfinite(v) or not (lo <= v <= hi):
        raise AttendanceError(f"{label} noto'g'ri yuborildi.", 400, "bad_coordinates")
    return v


def _dec(v):
    return None if v is None else Decimal(str(round(v, 6)))


def shift_date_for(schedule, now):
    """
    Smena sanasi = smena BOSHLANGAN kun. Oddiy smenada u bugungi sana. Tungi smenada (22:00–06:00) tugash
    vaqtigacha, ya'ni ertasi kuni ertalab kelgan xodim kechagi smenaga tegishli (kechagi kun ish kuni bo'lsa).
    """
    local = timezone.localtime(now)
    # Sutkalik smenada (08:00–08:00) ertalab oldinroq kelish keyingi smenaga tegishli; chiqish ochiq yozuvdan topiladi.
    if schedule is not None and schedule.crosses_midnight and not schedule.is_24h and local.time() < schedule.end_time:
        yesterday = local.date() - timedelta(days=1)
        if yesterday.weekday() in schedule.work_day_list():
            return yesterday
    return local.date()


def compute_status(schedule, now, shift_date=None):
    """(status, kechikish_daqiqa). Ish kuni bo'lmasa yoki jadval yo'q bo'lsa kechikish hisoblanmaydi."""
    local = timezone.localtime(now)
    day = shift_date or local.date()
    if schedule is None or day.weekday() not in schedule.work_day_list():
        return Attendance.Status.ON_TIME, 0
    start = timezone.make_aware(datetime.combine(day, schedule.start_time))
    if local > start + timedelta(minutes=schedule.grace_minutes):
        return Attendance.Status.LATE, int((local - start).total_seconds() // 60)
    return Attendance.Status.ON_TIME, 0


def _check_location(data, location):
    """Joylashuvni baholaydi (xato tashlamaydi). ok=True faqat klinika radiusida va aniqlik yetarli bo'lsa."""
    res = {"ok": False, "dist": None, "lat": None, "lng": None, "acc": None, "error": None}
    raw = [data.get("latitude"), data.get("longitude"), data.get("accuracy")]
    if all(v in (None, "") for v in raw):
        res["error"] = AttendanceError(
            "Joylashuv yuborilmadi. Brauzerda joylashuvga ruxsat bering.", 400, "no_location_data"
        )
        return res
    try:
        lat = _number(raw[0], "Kenglik", -90, 90)
        lng = _number(raw[1], "Uzunlik", -180, 180)
        acc = _number(raw[2], "GPS aniqligi", 0, 1_000_000)
    except AttendanceError as exc:
        res["error"] = exc
        return res
    dist = haversine_m(lat, lng, float(location.latitude), float(location.longitude))
    res.update(lat=lat, lng=lng, acc=acc, dist=dist)
    if acc > location.max_accuracy_m:
        res["error"] = AttendanceError(
            f"GPS aniqligi past (±{round(acc)} m, kerak: ±{location.max_accuracy_m} m gacha). "
            "Ochiq joyda, joylashuv xizmatini yoqib qayta urinib ko'ring.", 400, "low_accuracy",
        )
    elif dist > location.radius_m:
        res["error"] = AttendanceError(
            f"Siz klinika hududidan tashqaridasiz (taxminan {round(dist)} m, ruxsat: {location.radius_m} m).",
            403, "outside_radius",
        )
    else:
        res["ok"] = True
    return res


def _check_face(employee, image):
    """
    Yuzni baholaydi (xato tashlamaydi). `possible` — yuzni umuman tekshirish mumkinmi
    (kutubxona sozlangan va xodim ro'yxatdan o'tgan).
    """
    profile = FaceProfile.objects.filter(employee=employee, is_active=True).first()
    res = {"possible": False, "ok": False, "dist": None, "error": None}
    if not (face.is_available() and profile is not None):
        return res
    res["possible"] = True
    if image is None:
        res["error"] = AttendanceError("Yuz rasmi yuborilmadi. Kameraga ruxsat bering.", 400, "no_image")
        return res
    try:
        new_vec = face.embedding_from_image(image)
        known = face.decrypt_embedding(profile.encrypted_embedding)
    except face.FaceError as exc:
        res["error"] = AttendanceError(str(exc), 400, "face_error")
        return res
    res["dist"] = face.distance(new_vec, known)
    if res["dist"] <= settings.FACE_MATCH_TOLERANCE:
        res["ok"] = True
    else:
        res["error"] = AttendanceError("Yuz tasdiqlanmadi.", 403, "face_mismatch")
    return res


def _decide(location, loc, fc):
    """
    Davomat qabul qilinadimi? Qabul qilinsa yuz tasdiqlanganmi (bool) qaytaradi,
    aks holda AttendanceError tashlaydi.
    """
    if location.check_mode == ClinicLocation.CheckMode.BOTH:
        if loc["error"]:
            raise loc["error"]
        if fc["possible"]:
            if fc["error"]:
                raise AttendanceError(f"{fc['error'].message} Davomat qayd etilmadi.", fc["error"].status, fc["error"].code)
            return True
        if location.face_mode == ClinicLocation.FaceMode.STRICT:
            reason = (
                "Yuz verifikatsiyasi tizimda sozlanmagan." if not face.is_available()
                else "Yuzingiz tizimda ro'yxatdan o'tkazilmagan."
            )
            raise AttendanceError(f"{reason} Administrator bilan bog'laning.", 403, "face_not_configured")
        return False

    # EITHER: bittasi yetarli
    if loc["ok"] or fc["ok"]:
        return fc["ok"]
    if not fc["possible"]:
        raise loc["error"]  # yuz tekshirib bo'lmaydi: faqat joylashuv yo'li bor
    errors = [e for e in (fc["error"], loc["error"]) if e is not None]
    message = " ".join(e.message for e in errors) + " Davomat qayd etilmadi."
    status = 403 if any(e.status == 403 for e in errors) else 400
    code = fc["error"].code if fc["error"] and fc["error"].code in ("face_mismatch", "face_error") else loc["error"].code
    raise AttendanceError(message, status, code)


def open_overnight_record(employee, now, lock=False):
    """Kecha boshlangan va hali yopilmagan TUNGI smena yozuvi (xodim ertasi kuni chiqishni qayd etadi)."""
    qs = Attendance.objects.filter(
        employee=employee, check_in__isnull=False, check_out__isnull=True,
        check_in__gte=now - timedelta(hours=36), date__lt=timezone.localtime(now).date(),
        schedule_start__isnull=False, schedule_end__isnull=False,
    ).order_by("-date")
    if lock:
        qs = qs.select_for_update()
    for rec in qs:
        if rec.schedule_end <= rec.schedule_start:  # tungi yoki sutkalik smena nusxasi
            return rec
    return None


@transaction.atomic
def _write(employee, action, now, loc, verified, fdist):
    today = shift_date_for(employee.schedule, now)
    geo = dict(lat=_dec(loc["lat"]), lng=_dec(loc["lng"]), dist=loc["dist"], acc=loc["acc"], ok=loc["ok"])
    if action == "check_in":
        status, late = compute_status(employee.schedule, now, today)
        sched = employee.schedule
        try:
            with transaction.atomic():
                return Attendance.objects.create(
                    employee=employee, date=today, check_in=now, status=status, late_minutes=late,
                    schedule_start=sched.start_time if sched else None,
                    schedule_end=sched.end_time if sched else None,
                    in_face_verified=verified, in_face_distance=fdist, in_location_ok=geo["ok"],
                    in_latitude=geo["lat"], in_longitude=geo["lng"], in_distance_m=geo["dist"], in_accuracy_m=geo["acc"],
                )
        except IntegrityError:
            raise AttendanceError("Bugun ishga kelganingiz allaqachon qayd etilgan.", 409, "already_checked_in")

    rec = Attendance.objects.select_for_update().filter(employee=employee, date=today).first()
    if rec is None or rec.check_in is None:
        rec = open_overnight_record(employee, now, lock=True)
    if rec is None or rec.check_in is None:
        raise AttendanceError("Avval «Ishga keldim» tugmasini bosing.", 409, "no_check_in")
    if rec.check_out is not None:
        raise AttendanceError("Bugun ishdan ketganingiz allaqachon qayd etilgan.", 409, "already_checked_out")
    rec.check_out = now
    rec.out_face_verified = verified
    rec.out_face_distance = fdist
    rec.out_location_ok = geo["ok"]
    rec.out_latitude, rec.out_longitude = geo["lat"], geo["lng"]
    rec.out_distance_m, rec.out_accuracy_m = geo["dist"], geo["acc"]
    rec.save()
    return rec


def submit(request, employee, action, data, image):
    """action: 'check_in' | 'check_out'. Muvaffaqiyatda Attendance qaytaradi, aks holda AttendanceError."""
    loc = {"dist": None}
    fc = {"dist": None, "possible": False}
    try:
        location = ClinicLocation.objects.filter(is_active=True).order_by("id").first()
        if location is None:
            raise AttendanceError("Klinika joylashuvi hali sozlanmagan. Administratorga murojaat qiling.", 503, "no_location")

        loc = _check_location(data, location)
        fc = _check_face(employee, image)
        verified = _decide(location, loc, fc)
        record = _write(employee, action, timezone.now(), loc, verified, fc["dist"])
    except AttendanceError as exc:
        FaceAttemptLog.objects.create(
            employee=employee, action=action, success=False, reason=f"{exc.code}: {exc.message}"[:200],
            face_distance=fc.get("dist"), distance_m=loc.get("dist"),
        )
        log_action(request, f"attendance.{action}_rejected", details={"code": exc.code})
        raise

    note = ""
    if fc["possible"] and not fc["ok"]:
        note = "yuz tasdiqlanmadi, joylashuv bo'yicha qabul qilindi"
    elif not loc["ok"]:
        note = "yuz bo'yicha qabul qilindi, joylashuv tasdiqlanmadi"
    FaceAttemptLog.objects.create(
        employee=employee, action=action, success=True, reason=note,
        face_distance=fc["dist"], distance_m=loc["dist"],
    )
    log_action(request, f"attendance.{action}", record, {"face_verified": verified, "location_ok": loc["ok"]})
    return record

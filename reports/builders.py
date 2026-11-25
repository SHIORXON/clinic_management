"""Hisobot ma'lumotlarini yig'ish: har bir hisobot (columns, rows, summary) qaytaradi. Faqat administrator uchun."""
from datetime import date, timedelta

from django.utils import timezone

from attendance.models import Attendance
from employees.models import EmployeeProfile
from rewards.models import Bonus, DisciplinaryRecord
from tasks.models import Task, TaskAssignment
from tasks.serializers import OPEN_STATUSES, display_status

MAX_DAYS = 93
TITLES = {
    "attendance": "Davomat hisoboti",
    "tasks": "Topshiriqlar hisoboti",
    "bonuses": "Bonuslar hisoboti",
    "discipline": "Ogohlantirish va jarimalar hisoboti",
}


class ReportError(Exception):
    pass


def money(n):
    return f"{int(n):,}".replace(",", " ")


def parse_range(p):
    today = timezone.localdate()
    try:
        d_to = date.fromisoformat(p["date_to"]) if p.get("date_to") else today
        d_from = date.fromisoformat(p["date_from"]) if p.get("date_from") else d_to - timedelta(days=29)
    except ValueError:
        raise ReportError("Sana formati YYYY-MM-DD bo'lishi kerak.")
    if d_from > d_to:
        raise ReportError("Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.")
    if (d_to - d_from).days + 1 > MAX_DAYS:
        raise ReportError(f"Sana oralig'i {MAX_DAYS} kundan oshmasligi kerak.")
    return d_from, d_to


def _employees(p):
    qs = EmployeeProfile.objects.select_related("department", "schedule").filter(is_active=True)
    if p.get("employee"):
        qs = qs.filter(pk=p["employee"])
    if p.get("department"):
        qs = qs.filter(department_id=p["department"])
    if p.get("position"):
        qs = qs.filter(position__icontains=p["position"])
    return qs


def attendance_report(p):
    d_from, d_to = parse_range(p)
    today = timezone.localdate()
    emps = list(_employees(p))
    by_id = {e.id: e for e in emps}
    recs = Attendance.objects.filter(employee_id__in=by_id, date__range=(d_from, d_to))
    have = {(r.employee_id, r.date): r for r in recs}
    rows = []
    for e in emps:
        start = max(d_from, timezone.localtime(e.created_at).date())  # tizimga qo'shilgunga qadar "kelmadi" emas
        wd = set(e.schedule.work_day_list()) if e.schedule else set()
        d = d_from
        while d <= d_to:
            r = have.get((e.id, d))
            if r:
                rows.append((d, e, r.status, r))
            elif d >= start and d < today and d.weekday() in wd:
                rows.append((d, e, Attendance.Status.ABSENT, None))
            d += timedelta(days=1)
    st = p.get("status")
    if st in Attendance.Status.values:
        rows = [x for x in rows if x[2] == st]
    rows.sort(key=lambda x: (-x[0].toordinal(), x[1].full_name))
    labels = dict(Attendance.Status.choices)
    out = []
    for d, e, status, r in rows:
        out.append({
            "date": d.strftime("%d.%m.%Y"), "employee": e.full_name,
            "department": e.department.name if e.department else "-", "position": e.position,
            "check_in": timezone.localtime(r.check_in).strftime("%H:%M") if r and r.check_in else "-",
            "check_out": timezone.localtime(r.check_out).strftime("%H:%M") if r and r.check_out else "-",
            "status": labels[status], "status_code": status,
            "late": str(r.late_minutes) if r and r.late_minutes else "-",
        })
    summary = {
        "Jami yozuv": len(out),
        "O'z vaqtida": sum(1 for x in out if x["status_code"] == "on_time"),
        "Kechikkan": sum(1 for x in out if x["status_code"] == "late"),
        "Kelmagan": sum(1 for x in out if x["status_code"] == "absent"),
    }
    cols = [("date", "Sana"), ("employee", "Xodim"), ("department", "Bo'lim"), ("position", "Lavozim"),
            ("check_in", "Kelgan"), ("check_out", "Ketgan"), ("late", "Kechikish (daq)"), ("status", "Holat")]
    return cols, out, summary


def tasks_report(p):
    d_from, d_to = parse_range(p)
    today = timezone.localdate()
    qs = TaskAssignment.objects.select_related("task", "task__department", "employee", "employee__department") \
        .filter(task__due_date__range=(d_from, d_to), employee__in=_employees(p))
    st = p.get("status")
    if st == Task.Status.OVERDUE:
        qs = qs.filter(status__in=OPEN_STATUSES, task__due_date__lt=today)
    elif st in Task.Status.values:
        qs = qs.filter(status=st)
        if st in OPEN_STATUSES:
            qs = qs.filter(task__due_date__gte=today)
    out, counts = [], {}
    for a in qs.order_by("task__due_date", "employee__full_name"):
        ds = display_status(a, today)
        counts[ds] = counts.get(ds, 0) + 1
        out.append({
            "title": a.task.title, "employee": a.employee.full_name,
            "department": a.employee.department.name if a.employee.department else "-",
            "start": a.task.start_date.strftime("%d.%m.%Y"), "due": a.task.due_date.strftime("%d.%m.%Y"),
            "status": Task.Status(ds).label, "status_code": ds,
        })
    summary = {"Jami": len(out)}
    for code, label in Task.Status.choices:
        summary[label] = counts.get(code, 0)
    cols = [("title", "Topshiriq"), ("employee", "Xodim"), ("department", "Bo'lim"), ("start", "Boshlanish"),
            ("due", "Muddat"), ("status", "Holat")]
    return cols, out, summary


def bonuses_report(p):
    d_from, d_to = parse_range(p)
    qs = Bonus.objects.select_related("employee", "employee__department").filter(
        date__range=(d_from, d_to), is_cancelled=False, employee__in=_employees(p)).order_by("-date", "employee__full_name")
    out = [{"date": b.date.strftime("%d.%m.%Y"), "employee": b.employee.full_name,
            "department": b.employee.department.name if b.employee.department else "-",
            "reason": b.reason, "amount": money(b.amount)} for b in qs]
    summary = {"Bonuslar soni": len(out), "Jami summa (so'm)": money(sum(b.amount for b in qs))}
    cols = [("date", "Sana"), ("employee", "Xodim"), ("department", "Bo'lim"), ("reason", "Sabab"), ("amount", "Summa (so'm)")]
    return cols, out, summary


def discipline_report(p):
    d_from, d_to = parse_range(p)
    qs = DisciplinaryRecord.objects.select_related("employee", "employee__department").filter(
        date__range=(d_from, d_to), is_cancelled=False, employee__in=_employees(p))
    if p.get("kind") in DisciplinaryRecord.Kind.values:
        qs = qs.filter(kind=p["kind"])
    qs = qs.order_by("-date", "employee__full_name")
    out = [{"date": r.date.strftime("%d.%m.%Y"), "employee": r.employee.full_name,
            "department": r.employee.department.name if r.employee.department else "-",
            "kind": r.get_kind_display(), "reason": r.reason,
            "amount": money(r.amount) if r.amount else "-"} for r in qs]
    summary = {"Yozuvlar soni": len(out), "Jarimalar jami (so'm)": money(sum(r.amount for r in qs))}
    cols = [("date", "Sana"), ("employee", "Xodim"), ("department", "Bo'lim"), ("kind", "Turi"),
            ("reason", "Sabab"), ("amount", "Summa (so'm)")]
    return cols, out, summary


BUILDERS = {"attendance": attendance_report, "tasks": tasks_report, "bonuses": bonuses_report, "discipline": discipline_report}

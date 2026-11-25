from datetime import datetime, time, timedelta

from django.db.models import Sum
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import AuditLog
from accounts.permissions import IsActiveEmployee, require
from attendance.models import Attendance
from employees.models import EmployeeProfile
from notifications.models import Notification
from rewards.models import Bonus, DisciplinaryRecord
from tasks.models import Task, TaskAssignment

from . import builders, exporters

DAY_LABELS = ["Dush", "Sesh", "Chor", "Pay", "Jum", "Shan"]

# Audit amali -> faoliyat jurnalida ko'rinadigan matn. Ro'yxatda yo'q amallar (masalan, muvaffaqiyatsiz
# kirish urinishlari) jurnalda ko'rsatilmaydi.
ACTIVITY_TEXT = {
    "attendance.check_in": "ishga kelganini qayd etdi",
    "attendance.check_out": "ishdan ketganini qayd etdi",
    "attendance.check_in_rejected": "ishga kelishni qayd eta olmadi (rad etildi)",
    "attendance.check_out_rejected": "ishdan ketishni qayd eta olmadi (rad etildi)",
    "employee.create": "yangi xodim qo'shdi",
    "employee.update": "xodim ma'lumotini yangiladi",
    "employee.deactivate": "xodimni faolsizlantirdi",
    "employee.delete": "xodimni butunlay o'chirdi",
    "clinic_location.update": "klinika joylashuvini yangiladi",
    "face.enroll": "xodim yuzini ro'yxatdan o'tkazdi",
    "face.delete": "xodim yuz ma'lumotini o'chirdi",
    "department.create": "bo'lim qo'shdi",
    "department.update": "bo'limni yangiladi",
    "department.delete": "bo'limni o'chirdi",
    "schedule.create": "ish jadvali qo'shdi",
    "schedule.update": "ish jadvalini yangiladi",
    "schedule.delete": "ish jadvalini o'chirdi",
    "task.create": "yangi topshiriq berdi",
    "task.submit": "topshiriqni topshirdi",
    "task.review": "topshiriqni ko'rib chiqdi",
    "task.delete": "topshiriqni o'chirdi",
    "bonus.create": "bonus berdi",
    "bonus.cancel": "bonusni bekor qildi",
    "discipline.create": "ogohlantirish/jarima rasmiylashtirdi",
    "discipline.cancel": "ogohlantirish/jarimani bekor qildi",
}
DETAIL_KEYS = ("full_name", "employee", "name", "title")


class DashboardView(APIView):
    """
    Administrator bosh sahifasi uchun ko'rsatkichlar (bazadagi haqiqiy ma'lumotlardan).

    "Ishga kelmagan" = bugun ish kuni bo'lgan jadvalga ega faol xodimlardan, bugun davomati yo'q bo'lganlar.
    Ish jadvali biriktirilmagan xodim uchun bugun ish kuni yoki yo'qligini bilib bo'lmaydi, shuning uchun
    u "kelmagan" hisobiga kirmaydi.
    """

    permission_classes = [require("dashboard.view")]

    def get(self, request):
        today = timezone.localdate()
        weekday = today.weekday()

        active = list(EmployeeProfile.objects.filter(is_active=True).select_related("schedule"))
        expected = {e.id for e in active if e.schedule and weekday in e.schedule.work_day_list()}

        now = timezone.localtime()
        # Smenasi hali boshlanmagan (boshlanish + imtiyoz o'tmagan) xodim "kelmagan" hisoblanmaydi
        def started(e):
            start = timezone.make_aware(datetime.combine(today, e.schedule.start_time))
            return now >= start + timedelta(minutes=e.schedule.grace_minutes)
        expected = {e.id for e in active if e.id in expected and started(e)}

        today_qs = Attendance.objects.filter(date=today, check_in__isnull=False)
        present_ids = set(today_qs.values_list("employee_id", flat=True))
        # Kecha boshlangan va hali davom etayotgan tungi smenalar ham "ishda"
        for r in Attendance.objects.filter(date=today - timedelta(days=1), check_in__isnull=False, check_out__isnull=True,
                                           schedule_start__isnull=False, schedule_end__isnull=False):
            if r.schedule_end <= r.schedule_start:
                present_ids.add(r.employee_id)
        late = today_qs.filter(status=Attendance.Status.LATE).count()

        monday = today - timedelta(days=weekday)
        weekly = []
        for i, label in enumerate(DAY_LABELS):
            d = monday + timedelta(days=i)
            day_qs = Attendance.objects.filter(date=d, check_in__isnull=False)
            total = day_qs.count()
            late_n = day_qs.filter(status=Attendance.Status.LATE).count()
            weekly.append({"day": label, "kelgan": total, "vaqtida": total - late_n})

        activity = []
        for log in AuditLog.objects.filter(action__in=ACTIVITY_TEXT).select_related("actor")[:8]:
            what = ACTIVITY_TEXT[log.action]
            detail = next((log.details[k] for k in DETAIL_KEYS if isinstance(log.details, dict) and log.details.get(k)), None)
            if detail and log.action.startswith(("employee.", "face.", "department.", "schedule.", "task.create", "bonus.", "discipline.")):
                what = f"{what}: {detail}"
            activity.append({
                "who": log.actor.full_name if log.actor else "Tizim",
                "what": what,
                "when": log.created_at,
            })

        open_asg = TaskAssignment.objects.filter(status__in=(Task.Status.NEW, Task.Status.IN_PROGRESS, Task.Status.REWORK))
        month_start = today.replace(day=1)
        bonus_qs = Bonus.objects.filter(is_cancelled=False, date__gte=month_start)
        disc_qs = DisciplinaryRecord.objects.filter(is_cancelled=False, date__gte=month_start)
        tasks_weekly = []
        for i, label in enumerate(DAY_LABELS):
            d = monday + timedelta(days=i)
            lo = timezone.make_aware(datetime.combine(d, time.min))
            hi = lo + timedelta(days=1)
            tasks_weekly.append({
                "day": label,
                # `__date` o'rniga vaqt oralig'i: MySQL'da vaqt zonasi jadvallarini talab qilmaydi
                "berilgan": TaskAssignment.objects.filter(assigned_at__gte=lo, assigned_at__lt=hi).count(),
                "bajarilgan": TaskAssignment.objects.filter(
                    status=Task.Status.APPROVED, task__updated_at__gte=lo, task__updated_at__lt=hi).count(),
            })

        return Response({
            "date": today,
            "tasks_in_progress": TaskAssignment.objects.filter(status=Task.Status.IN_PROGRESS).count(),
            "tasks_to_review": TaskAssignment.objects.filter(status=Task.Status.SUBMITTED).count(),
            "tasks_overdue": open_asg.filter(task__due_date__lt=today).count(),
            "bonus_count_month": bonus_qs.count(),
            "bonus_sum_month": bonus_qs.aggregate(s=Sum("amount"))["s"] or 0,
            "discipline_count_month": disc_qs.count(),
            "tasks_weekly": tasks_weekly,
            "total_employees": len(active),
            "expected_today": len(expected),
            "present_today": len(present_ids),
            "late_today": late,
            "absent_today": len(expected - present_ids),
            "weekly": weekly,
            "activity": activity,
        })


class ReportView(APIView):
    """/api/reports/<kind>/?date_from&date_to&employee&department&position&status[&export=xlsx|pdf]. Faqat administrator."""

    permission_classes = [require("reports.view")]
    PAGE = 50

    def get(self, request, kind):
        builder = builders.BUILDERS.get(kind)
        if not builder:
            return Response({"detail": "Bunday hisobot yo'q."}, status=404)
        try:
            cols, rows, summary = builder(request.query_params)
            d_from, d_to = builders.parse_range(request.query_params)
        except builders.ReportError as e:
            return Response({"detail": str(e)}, status=400)
        except (ValueError, TypeError):
            return Response({"detail": "Noto'g'ri filtr qiymati."}, status=400)
        title = builders.TITLES[kind]
        fmt = request.query_params.get("export")
        if fmt:
            if fmt not in ("xlsx", "pdf"):
                return Response({"detail": "export qiymati xlsx yoki pdf bo'lishi kerak."}, status=400)
            sub = f"Davr: {d_from:%d.%m.%Y} — {d_to:%d.%m.%Y}"
            return exporters.export_response(kind, fmt, title, cols, rows, summary, sub)
        try:
            page = max(int(request.query_params.get("page", 1)), 1)
        except ValueError:
            page = 1
        start = (page - 1) * self.PAGE
        return Response({
            "title": title, "count": len(rows), "page_size": self.PAGE,
            "next": page * self.PAGE < len(rows) or None, "previous": page > 1 or None,
            "columns": [{"key": k, "label": h} for k, h in cols],
            "summary": summary, "results": rows[start:start + self.PAGE],
            "date_from": d_from, "date_to": d_to,
        })


class SummaryView(APIView):
    """Menyu belgilari va xodim bosh sahifasi uchun qisqa ko'rsatkichlar."""

    permission_classes = [IsActiveEmployee]

    def get(self, request):
        me = request.user.profile
        today = timezone.localdate()
        month_start = today.replace(day=1)
        unread = Notification.objects.filter(recipient=me, is_read=False).count()
        extra = {}
        if me.can("tasks.manage"):
            extra["tasks_to_review"] = TaskAssignment.objects.filter(status=Task.Status.SUBMITTED).count()
        mine = TaskAssignment.objects.filter(employee=me)
        open_q = mine.filter(status__in=(Task.Status.NEW, Task.Status.IN_PROGRESS, Task.Status.REWORK))
        bonus = Bonus.objects.filter(employee=me, is_cancelled=False, date__gte=month_start)
        disc = DisciplinaryRecord.objects.filter(employee=me, is_cancelled=False, date__gte=month_start)
        return Response({
            "unread": unread,
            "open_tasks": open_q.count(),
            "overdue_tasks": open_q.filter(task__due_date__lt=today).count(),
            "submitted_tasks": mine.filter(status=Task.Status.SUBMITTED).count(),
            "bonus_sum_month": bonus.aggregate(s=Sum("amount"))["s"] or 0,
            "discipline_count_month": disc.count(),
            "fine_sum_month": disc.aggregate(s=Sum("amount"))["s"] or 0,
            **extra,
        })

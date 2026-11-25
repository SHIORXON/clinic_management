import os

from django.http import FileResponse, Http404
from django.utils import timezone
from rest_framework import status as http
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.audit import log_action
from accounts.permissions import IsActiveEmployee, sees_all
from notifications.services import notify, notify_managers

from .models import Task, TaskAssignment, TaskSubmission
from .serializers import (OPEN_STATUSES, AssignmentSerializer, TaskCreateSerializer, TaskUpdateSerializer,
                          validate_upload)


class TaskViewSet(viewsets.GenericViewSet):
    """
    Vazifalar xodim bo'yicha (TaskAssignment) yuritiladi. Xodim faqat o'ziga biriktirilganini ko'radi
    (boshqasiniki 404). Yaratish, tahrirlash, o'chirish va ko'rib chiqish faqat administratorga.
    """

    serializer_class = AssignmentSerializer
    permission_classes = [IsActiveEmployee]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_queryset(self):
        me = self.request.user.profile
        qs = TaskAssignment.objects.select_related(
            "task", "task__department", "task__created_by", "employee"
        ).prefetch_related("submissions", "submissions__reviewed_by")
        if self.action == "list":
            return qs if sees_all(self.request, "tasks") else qs.filter(employee=me)
        if self.action == "retrieve":
            return qs if me.can("tasks.view") else qs.filter(employee=me)
        if self.action in ("partial_update", "destroy", "review"):
            return qs  # tasks.manage ruxsati _admin_only da tekshiriladi
        return qs.filter(employee=me)  # start / submit: faqat o'ziniki

    def _admin_only(self, request):
        if not request.user.profile.can("tasks.manage"):
            return Response({"detail": "Bu amal uchun sizda ruxsat yo'q."}, status=403)
        return None

    def filter_queryset(self, qs):
        p = self.request.query_params
        today = timezone.localdate()
        st = p.get("status")
        if st == Task.Status.OVERDUE:
            qs = qs.filter(status__in=OPEN_STATUSES, task__due_date__lt=today)
        elif st in Task.Status.values:
            qs = qs.filter(status=st)
            if st in OPEN_STATUSES:  # "yangi" ro'yxatida muddati o'tganlar ko'rinmasin
                qs = qs.filter(task__due_date__gte=today)
        if sees_all(self.request, "tasks"):
            if p.get("employee"):
                qs = qs.filter(employee_id=p["employee"])
            if p.get("department"):
                qs = qs.filter(employee__department_id=p["department"])
            if p.get("search"):
                qs = qs.filter(task__title__icontains=p["search"].strip())
        return qs.order_by("task__due_date", "-id")

    def list(self, request):
        try:
            page = self.paginate_queryset(self.filter_queryset(self.get_queryset()))
        except (ValueError, TypeError):
            return Response({"detail": "Noto'g'ri filtr qiymati."}, status=400)
        return self.get_paginated_response(self.get_serializer(page, many=True).data)

    def retrieve(self, request, pk=None):
        return Response(self.get_serializer(self.get_object()).data)

    def create(self, request):
        denied = self._admin_only(request)
        if denied:
            return denied
        ser = TaskCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        me = request.user.profile
        task = Task.objects.create(
            title=d["title"], description=d["description"], department=d.get("department"),
            start_date=d["start_date"], due_date=d["due_date"], created_by=me,
        )
        assignments = [TaskAssignment.objects.create(task=task, employee=e) for e in d["assignees"]]
        notify([a.employee for a in assignments], "Yangi topshiriq", f"{task.title} — muddat: {task.due_date:%d.%m.%Y}", "/tasks")
        log_action(request, "task.create", task, {"title": task.title, "employees": len(assignments)})
        return Response(self.get_serializer(assignments, many=True).data, status=http.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        denied = self._admin_only(request)
        if denied:
            return denied
        a = self.get_object()
        ser = TaskUpdateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        t = a.task
        for k, v in ser.validated_data.items():
            setattr(t, k, v)
        if t.due_date < t.start_date:
            return Response({"due_date": ["Muddat boshlanish sanasidan oldin bo'lishi mumkin emas."]}, status=400)
        t.save()
        notify([x.employee for x in t.assignments.all()], "Topshiriq yangilandi", t.title, "/tasks")
        log_action(request, "task.update", t, {"title": t.title})
        return Response(self.get_serializer(self.get_object()).data)

    def destroy(self, request, pk=None):
        denied = self._admin_only(request)
        if denied:
            return denied
        a = self.get_object()
        t = a.task
        log_action(request, "task.delete", t, {"title": t.title})
        t.delete()  # barcha xodimlardagi nusxasi bilan
        return Response(status=http.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        a = self.get_object()
        if a.employee_id != request.user.profile.id:
            return Response({"detail": "Faqat o'zingizga biriktirilgan topshiriqni boshlay olasiz."}, status=403)
        if a.status not in (Task.Status.NEW, Task.Status.REWORK):
            return Response({"detail": "Bu topshiriqni boshlab bo'lmaydi."}, status=400)
        a.status = Task.Status.IN_PROGRESS
        a.save(update_fields=["status"])
        return Response(self.get_serializer(a).data)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        a = self.get_object()
        me = request.user.profile
        if a.employee_id != me.id:
            return Response({"detail": "Faqat o'zingizga biriktirilgan topshiriqni topshira olasiz."}, status=403)
        if a.status not in OPEN_STATUSES:
            return Response({"detail": "Bu topshiriq allaqachon topshirilgan yoki tasdiqlangan."}, status=400)
        comment = (request.data.get("comment") or "").strip()
        f = request.FILES.get("file")
        if not comment and not f:
            return Response({"detail": "Izoh yozing yoki fayl biriktiring."}, status=400)
        if f:
            from rest_framework.exceptions import ValidationError
            try:
                validate_upload(f)
            except ValidationError as e:
                return Response({"file": e.detail}, status=400)
        TaskSubmission.objects.create(assignment=a, comment=comment, file=f)
        a.status = Task.Status.SUBMITTED
        a.save(update_fields=["status"])
        notify_managers("tasks.manage", "Topshiriq topshirildi", f"{me.full_name}: {a.task.title}", "/tasks", exclude=me)
        log_action(request, "task.submit", a.task, {"employee": me.full_name, "title": a.task.title})
        return Response(self.get_serializer(self.get_object()).data)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        denied = self._admin_only(request)
        if denied:
            return denied
        a = self.get_object()
        if a.status != Task.Status.SUBMITTED:
            return Response({"detail": "Faqat topshirilgan topshiriqni ko'rib chiqish mumkin."}, status=400)
        approved = request.data.get("approved")
        if isinstance(approved, str):
            approved = approved.lower() in ("1", "true")
        if approved not in (True, False):
            return Response({"approved": ["true yoki false bo'lishi kerak."]}, status=400)
        comment = (request.data.get("comment") or "").strip()
        if not approved and not comment:
            return Response({"comment": ["Qayta ishlashga qaytarishda sababini yozing."]}, status=400)
        sub = a.submissions.first()
        now = timezone.now()
        sub.approved, sub.reviewed_by, sub.reviewed_at, sub.review_comment = approved, request.user.profile, now, comment
        sub.save()
        a.status = Task.Status.APPROVED if approved else Task.Status.REWORK
        a.save(update_fields=["status"])
        notify(a.employee, "Topshiriq tasdiqlandi" if approved else "Topshiriq qayta ishlashga qaytarildi",
               a.task.title + (f" — {comment}" if comment else ""), "/tasks")
        log_action(request, "task.review", a.task, {"employee": a.employee.full_name, "approved": approved})
        return Response(self.get_serializer(self.get_object()).data)


class SubmissionFileView(APIView):
    """Topshirilgan faylni faqat egasi yoki administrator yuklab olishi mumkin (ommaviy MEDIA yo'q)."""

    permission_classes = [IsActiveEmployee]

    def get(self, request, pk):
        sub = TaskSubmission.objects.select_related("assignment").filter(pk=pk).first()
        me = request.user.profile
        if not sub or not sub.file or not (me.can("tasks.view") or sub.assignment.employee_id == me.id):
            raise Http404
        try:
            fh = sub.file.open("rb")
        except FileNotFoundError:
            raise Http404
        return FileResponse(fh, as_attachment=True, filename=os.path.basename(sub.file.name))

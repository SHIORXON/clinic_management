from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("tasks", views.TaskViewSet, basename="tasks")

urlpatterns = [
    path("tasks/files/<int:pk>/", views.SubmissionFileView.as_view(), name="task-file"),
] + router.urls

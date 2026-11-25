from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("attendance", views.AttendanceViewSet, basename="attendance")

# Aniq manzillar router'dan oldin turishi shart ("today" pk deb tushunilmasligi uchun).
urlpatterns = [
    path("attendance/today/", views.TodayView.as_view(), name="attendance-today"),
    path("attendance/check-in/", views.CheckInView.as_view(), name="attendance-check-in"),
    path("attendance/check-out/", views.CheckOutView.as_view(), name="attendance-check-out"),
    path("attendance/location/", views.LocationView.as_view(), name="attendance-location"),
    path("attendance/face/<int:employee_id>/", views.FaceEnrollView.as_view(), name="attendance-face"),
] + router.urls

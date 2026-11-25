from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter()
router.register("employees", views.EmployeeViewSet, basename="employee")
router.register("departments", views.DepartmentViewSet, basename="department")
router.register("schedules", views.WorkScheduleViewSet, basename="schedule")

urlpatterns = router.urls

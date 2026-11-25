from django.urls import path

from . import views

urlpatterns = [
    path("reports/dashboard/", views.DashboardView.as_view(), name="reports-dashboard"),
    path("reports/summary/", views.SummaryView.as_view(), name="reports-summary"),
    path("reports/<str:kind>/", views.ReportView.as_view(), name="reports-report"),
]

from django.contrib import admin
from django.urls import include, path, re_path

from . import pwa, views

urlpatterns = [
    path("", views.index, name="index"),
    path("sw.js", pwa.service_worker, name="sw"),
    path("offline/", pwa.offline, name="offline"),
    path("privacy/", pwa.privacy, name="privacy"),
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path(".well-known/assetlinks.json", pwa.assetlinks, name="assetlinks"),
    # Frontend sahifalari (# siz oddiy manzillar): /employees, /manage/tasks va hokazo
    re_path(r"^(?:dashboard|tasks|warnings|bonuses|employees|attendance|reports|settings|profile|home|manage/[a-z]+)/?$",
            views.index, name="spa"),
    path("django-admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("employees.urls")),
    path("api/", include("attendance.urls")),
    path("api/", include("tasks.urls")),
    path("api/", include("rewards.urls")),
    path("api/", include("notifications.urls")),
    path("api/", include("reports.urls")),
]

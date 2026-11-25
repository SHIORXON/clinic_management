"""PWA / Android (TWA) uchun xizmat fayllari: manifest, service worker, offline sahifa, Digital Asset Links."""
from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


def _static_file(name):
    path = settings.BASE_DIR / "static" / "pwa" / name
    if not path.exists():
        raise Http404
    return path


@never_cache
def service_worker(request):
    # Scope "/" bo'lishi uchun ildizdan beriladi
    resp = FileResponse(open(_static_file("sw.js"), "rb"), content_type="text/javascript")
    resp["Service-Worker-Allowed"] = "/"
    return resp


def offline(request):
    return FileResponse(open(_static_file("offline.html"), "rb"), content_type="text/html; charset=utf-8")


def manifest(request):
    return JsonResponse({
        "name": "Gold Med Clinic — Boshqaruv",
        "short_name": "Gold Med",
        "description": "Klinika xodimlari davomati, topshiriqlari va hisobotlari",
        "lang": "uz",
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#F5F2EB",
        "theme_color": "#132A2E",
        "icons": [
            {"src": "/static/pwa/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/pwa/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": "/static/pwa/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, content_type="application/manifest+json")


def assetlinks(request):
    """
    Play Market ilovasi (TWA) ushbu saytga tegishli ekanini tasdiqlaydi. Aks holda ilova tepasida brauzer
    paneli chiqib qoladi. Paket nomi va imzo barmoq izi .env dan olinadi (README, «Android ilova»).
    """
    pkg = settings.ANDROID_PACKAGE_NAME
    prints = settings.ANDROID_SHA256_FINGERPRINTS
    if not pkg or not prints:
        return JsonResponse([], safe=False)
    return JsonResponse([{
        "relation": ["delegate_permission/common.handle_all_urls"],
        "target": {"namespace": "android_app", "package_name": pkg, "sha256_cert_fingerprints": prints},
    }], safe=False)


def privacy(request):
    """Maxfiylik siyosati (Play Market uchun ommaviy URL). Matn namuna: klinika yurist bilan ko'rib chiqishi kerak."""
    return render(request, "privacy.html", {
        "clinic_name": settings.CLINIC_NAME,
        "contact": settings.PRIVACY_CONTACT or "Aloqa ma'lumoti hali kiritilmagan (.env: PRIVACY_CONTACT).",
        "updated": "2026",
    })

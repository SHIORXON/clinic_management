from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie

from accounts.views import me_payload


@never_cache
@ensure_csrf_cookie
def index(request):
    """
    Frontend (React) sahifasi. Bu HTML'ning o'zida maxfiy ma'lumot yo'q: ma'lumotlar faqat
    himoyalangan API orqali olinadi. Kirgan foydalanuvchi bo'lsa, uning ma'lumoti sahifaga qo'shiladi
    (login oynasi bir lahzaga ham ko'rinib qolmasligi uchun); CSRF cookie ham shu yerda o'rnatiladi.
    """
    boot = None
    if request.user.is_authenticated:
        profile = getattr(request.user, "profile", None)
        if profile is not None and profile.is_active:
            boot = me_payload(request.user)
    return render(request, "index.html", {"boot": boot})

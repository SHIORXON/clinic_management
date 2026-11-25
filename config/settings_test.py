"""Testlarni MySQL'siz (SQLite xotirada) tez ishga tushirish uchun:
    python manage.py test --settings=config.settings_test
Haqiqiy tekshiruvdan oldin MySQL bilan ham ishga tushiring (oddiy `python manage.py test`)."""
from .settings import *  # noqa: F401,F403

DEBUG = True
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # faqat testlar tezligi uchun
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {"user": "10000/min", "login": "10000/min", "attendance": "10000/min"},
}

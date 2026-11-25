from datetime import time

from django.core.management.base import BaseCommand

from employees.models import Department, WorkSchedule

DEPARTMENTS = ["Qabulxona", "Laboratoriya", "Xo'jalik", "Buxgalteriya", "SMM", "Boshqaruv"]

# Tayyor smena namunalari (administrator Sozlamalar bo'limida o'zgartirishi yoki yangisini qo'shishi mumkin)
SHIFTS = [
    ("Ertalabki smena (07:00–15:00)", time(7, 0), time(15, 0), "0,1,2,3,4,5"),
    ("Kechki smena (15:00–23:00)", time(15, 0), time(23, 0), "0,1,2,3,4,5"),
    ("Tungi smena (22:00–06:00)", time(22, 0), time(6, 0), "0,1,2,3,4,5,6"),
    ("Sutkalik navbatchilik (08:00–08:00)", time(8, 0), time(8, 0), "0,1,2,3,4,5,6"),
]


class Command(BaseCommand):
    help = (
        "Boshlang'ich bo'limlar va standart ish jadvalini yaratadi (mavjud bo'lsa tegmaydi). "
        "Soxta xodim yoki klinika koordinatalari YARATILMAYDI: ularni administrator o'zi kiritadi."
    )

    def handle(self, *args, **options):
        for name in DEPARTMENTS:
            _, created = Department.objects.get_or_create(name=name)
            self.stdout.write(f"{'+' if created else '='} Bo'lim: {name}")
        _, created = WorkSchedule.objects.get_or_create(
            name="Standart (Du–Sha 09:00–18:00)",
            defaults={"start_time": time(9, 0), "end_time": time(18, 0), "grace_minutes": 10, "work_days": "0,1,2,3,4,5"},
        )
        self.stdout.write(f"{'+' if created else '='} Ish jadvali: Standart")
        for name, start, end, days in SHIFTS:
            _, created = WorkSchedule.objects.get_or_create(
                name=name, defaults={"start_time": start, "end_time": end, "grace_minutes": 10, "work_days": days}
            )
            self.stdout.write(f"{'+' if created else '='} Ish jadvali: {name}")
        self.stdout.write(self.style.SUCCESS("Tayyor."))

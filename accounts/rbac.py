"""
Ruxsatlar (RBAC): administrator har bir xodimga qaysi bo'limlarni ko'rish va qaysi amallarni bajarishni belgilaydi.

- `admin` roli: hamma narsaga ruxsat (ruxsatlar ro'yxati kerak emas).
- `employee` roli: o'z ma'lumotlari (bosh sahifa, davomat tarixi, o'z topshiriqlari, bonus va ogohlantirishlari)
  har doim ochiq; qo'shimcha bo'limlar `EmployeeProfile.permissions` ro'yxati orqali beriladi.
- `<bo'lim>.manage` ruxsati `<bo'lim>.view` ni o'z ichiga oladi.
"""

# (bo'lim kaliti, nomi, [(ruxsat kodi, nomi, izoh)])
SECTIONS = [
    ("dashboard", "Boshqaruv paneli", [
        ("dashboard.view", "Ko'rish", "Bugungi ish holati va umumiy ko'rsatkichlar"),
    ]),
    ("employees", "Xodimlar", [
        ("employees.view", "Ko'rish", "Xodimlar ro'yxati va ma'lumotlari"),
        ("employees.manage", "Boshqarish", "Xodim qo'shish, tahrirlash, faolsizlantirish, yuzini ro'yxatdan o'tkazish"),
    ]),
    ("attendance", "Davomat (hammaning)", [
        ("attendance.view", "Ko'rish", "Barcha xodimlarning davomat yozuvlari"),
    ]),
    ("tasks", "Topshiriqlar", [
        ("tasks.view", "Ko'rish", "Barcha topshiriqlar"),
        ("tasks.manage", "Boshqarish", "Topshiriq berish, tahrirlash, o'chirish, topshirilganini tasdiqlash"),
    ]),
    ("bonuses", "Bonus", [
        ("bonuses.view", "Ko'rish", "Barcha bonuslar"),
        ("bonuses.manage", "Boshqarish", "Bonus berish, tahrirlash, bekor qilish"),
    ]),
    ("discipline", "Ogohlantirish / Jarima", [
        ("discipline.view", "Ko'rish", "Barcha ogohlantirish, jarima va hayfsanlar"),
        ("discipline.manage", "Boshqarish", "Yozuv qo'shish, tahrirlash, bekor qilish"),
    ]),
    ("reports", "Hisobotlar", [
        ("reports.view", "Ko'rish va yuklab olish", "Davomat, topshiriq, bonus va jarima hisobotlari (Excel, PDF)"),
    ]),
    ("settings", "Sozlamalar", [
        ("settings.manage", "Boshqarish", "Klinika joylashuvi, bo'limlar, ish jadvallari, davomat qoidalari"),
    ]),
]

ALL_CODES = [code for _, _, items in SECTIONS for code, _, _ in items]
_ALL = set(ALL_CODES)

# Tayyor rol shablonlari (administrator formada bir bosishda tanlaydi, keyin o'zgartirishi mumkin).
PRESETS = [
    {"id": "employee", "label": "Oddiy xodim", "role": "employee", "permissions": []},
    {"id": "department_head", "label": "Bo'lim boshlig'i", "role": "employee", "permissions": [
        "dashboard.view", "attendance.view", "tasks.view", "tasks.manage", "bonuses.view", "discipline.view",
    ]},
    {"id": "manager", "label": "Menejer", "role": "employee", "permissions": [
        "dashboard.view", "employees.view", "attendance.view", "tasks.view", "tasks.manage", "reports.view",
    ]},
    {"id": "hr", "label": "Kadrlar bo'limi", "role": "employee", "permissions": [
        "dashboard.view", "employees.view", "employees.manage", "attendance.view", "reports.view",
    ]},
    {"id": "accountant", "label": "Buxgalter", "role": "employee", "permissions": [
        "dashboard.view", "attendance.view", "bonuses.view", "discipline.view", "reports.view",
    ]},
    {"id": "admin", "label": "Administrator (to'liq huquq)", "role": "admin", "permissions": []},
]


def normalize(codes):
    """Noma'lum kodlarni tashlaydi, `.manage` uchun `.view` ni qo'shadi, tartiblangan ro'yxat qaytaradi."""
    result = set()
    for c in codes or []:
        if c in _ALL:
            result.add(c)
            if c.endswith(".manage") and c[:-7] + ".view" in _ALL:
                result.add(c[:-7] + ".view")
    return sorted(result, key=ALL_CODES.index)


def unknown(codes):
    return [c for c in (codes or []) if c not in _ALL]


def catalog():
    return {
        "sections": [
            {"key": key, "label": label, "items": [{"code": c, "label": l, "help": h} for c, l, h in items]}
            for key, label, items in SECTIONS
        ],
        "presets": PRESETS,
    }

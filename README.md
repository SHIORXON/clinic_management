# Gold Med — Klinika xodimlari faoliyatini boshqarish tizimi

Django + Django REST Framework + MySQL. Frontend — taqdim etilgan `index.html` dizayni (React + Tailwind),
`frontend/src/app.jsx` ga ko'chirilgan va backend bilan ulangan. Asl fayl nusxasi: `docs/original_index.html`.

## Hozirgi holat

| Modul | Holat |
|---|---|
| Login / logout / rollar (administrator, xodim) / parolni almashtirish | tayyor |
| Xodimlar, bo'limlar, ish jadvallari | tayyor |
| Davomat (server vaqti, GPS radius, kechikish), tarix | tayyor |
| Yuz verifikatsiyasi, «yuz YOKI joylashuv» usuli | tayyor; yuz kutubxonasini o'rnatish kerak (4-bo'lim) |
| Bosh panel (haqiqiy ma'lumotlardan: davomat, topshiriqlar, bonus, intizom, faoliyat jurnali) | tayyor |
| Topshiriqlar (bir yoki bir nechta xodimga; boshlash, fayl bilan topshirish, tasdiqlash / qayta ishlashga qaytarish) | tayyor |
| Bonus va Ogohlantirish/Jarima (admin qo'shadi, tahrirlaydi, **bekor qiladi** — o'chirish yo'q) | tayyor |
| Bildirishnomalar (qo'ng'iroqcha, o'qilmaganlar soni) | tayyor |
| Hisobotlar: davomat, topshiriqlar, bonus, intizom; filtrlar; **Excel va PDF** yuklab olish | tayyor |

Asl `index.html` dagi Prayskurant, Shifokorlar, Muhokamalar, Takliflar, Majlislar va Hujjatlar bo'limlari
talab etilgan 13 ta modelga kirmagani uchun menyudan olib tashlandi.

## 1. O'rnatish (Windows)

1. **Python 3.11 yoki 3.12** (python.org; o'rnatishda «Add Python to PATH» belgilansin).
2. **MySQL 8.0.16+** (dev.mysql.com) yoki MariaDB 10.5+; o'rnatishda `root` paroli so'raladi, eslab qoling.
3. MySQL Command Line Client (yoki Workbench) da bazani yarating:
   ```sql
   CREATE DATABASE clinic_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'clinic_user'@'localhost' IDENTIFIED BY 'sizning-parolingiz';
   GRANT ALL PRIVILEGES ON clinic_db.* TO 'clinic_user'@'localhost';
   GRANT ALL PRIVILEGES ON `test\_clinic_db`.* TO 'clinic_user'@'localhost';  -- faqat `manage.py test` uchun
   FLUSH PRIVILEGES;
   ```
4. Loyiha papkasida (`cmd`):
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   ```
   `.env` ni oching va kamida `DB_PASSWORD` hamda `DJANGO_SECRET_KEY` (uzun tasodifiy matn) ni to'ldiring.
5. Bazani tayyorlang va ishga tushiring:
   ```
   python manage.py migrate
   python manage.py seed_initial          # boshlang'ich bo'limlar va standart ish jadvali (ixtiyoriy)
   python manage.py createsuperuser       # birinchi administrator
   python manage.py runserver
   ```
6. Brauzerda `http://127.0.0.1:8000/` ni oching va superuser login/paroli bilan kiring.

> Frontend kutubxonalari (React, Tailwind, Babel, Recharts, Lucide) internetdan (CDN) yuklanadi, shuning uchun
> kompyuter internetga ulangan bo'lishi kerak. Server (production) uchun ularni oldindan qurish (build) tavsiya etiladi.

Texnik panel: `http://127.0.0.1:8000/django-admin/` (jadvallarni to'g'ridan-to'g'ri ko'rish uchun).

### Har kuni ishga tushirish (oson yo'l)
`start.bat` faylini ikki marta bosing: u bazani yangilaydi, tizimni ishga tushiradi va brauzerda ochadi.
Chrome'da manzil qatoridagi «O'rnatish» belgisini (yoki ⋮ → «Gold Med ni o'rnatish») bossangiz, tizim alohida
oynali ilova bo'lib ish stolida turadi.

## 2. Birinchi sozlash (administrator)

1. **Sozlamalar → Klinika joylashuvi:** klinikada turib «Hozirgi joylashuvimni olish» ni bosing (yoki Google Maps dan
   koordinatani kiriting), radiusni belgilang (standart 100 m), «Saqlash». **Bu qilinmaguncha hech kim davomat qila olmaydi.**
2. **Sozlamalar → Ish jadvallari:** ish vaqtini va kechikish imtiyozini belgilang. Xodimga jadval biriktirilmasa,
   uning kechikishi hisoblanmaydi va u «ishga kelmagan» hisobiga kirmaydi.
3. **Xodimlar → Yangi xodim:** login, parol, lavozim, bo'lim, jadval. Xodimga login/parolni o'zingiz bering.

## 3. Telefondan davomat qilish (HTTPS shart)

Brauzer **kamera va joylashuvni faqat HTTPS yoki `localhost` da** beradi. Telefonda `http://192.168.x.x:8000` ishlamaydi.
Sinash uchun eng oson yo'l — HTTPS tunnel (masalan, `ngrok http 8000` yoki `cloudflared tunnel --url http://localhost:8000`):

1. Tunnel bergan manzilni (masalan `abc123.ngrok-free.app`) `.env` ga qo'shing:
   ```
   DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,abc123.ngrok-free.app
   CSRF_TRUSTED_ORIGINS=https://abc123.ngrok-free.app
   ```
2. Serverni qayta ishga tushiring va telefonda shu HTTPS manzilni oching.

Doimiy ishlash uchun serverda haqiqiy domen va SSL sertifikat kerak (pastdagi «Serverga joylashtirish»).

## 4. Yuz verifikatsiyasi

**Muhim:** telefonning Face ID / barmoq izi faqat *qurilma egasini* tasdiqlaydi, klinika bazasidagi xodim yuzi bilan
solishtirmaydi. Shuning uchun yuz serverda `face_recognition` (dlib) kutubxonasi bilan tekshiriladi.
Kamera ochilishi yoki suratga olish o'z-o'zidan yuzni tanish degani emas.

### Davomat tasdiqlash usuli (Sozlamalar → «Davomat tasdiqlash usuli»)

| Usul | Qoida |
|---|---|
| **Yuz YOKI joylashuv** (standart) | Klinika radiusida bo'lsa **yoki** yuzi mos kelsa, davomat qabul qilinadi. Bittasi yetarli. |
| **Yuz VA joylashuv** | Joylashuv shart. Yuzi ro'yxatdan o'tgan xodimning yuzi ham mos kelishi shart. |

«Yoki» usulida: yuz ro'yxatdan o'tmagan xodim uchun (yoki kutubxona sozlanmagan bo'lsa) faqat joylashuv yo'li ishlaydi.
Yuzi mos kelgan xodim klinikadan tashqarida turib ham davomat qila oladi, bunday yozuvlar davomat jadvalida
**«Tashqarida»** deb ko'rinadi, shuning uchun administrator ularni ajrata oladi.
«VA» usulida yuzni tekshirib bo'lmasa nima bo'lishi alohida tanlanadi: yumshoq (joylashuv bo'yicha qayd etiladi,
«yuz tekshirilmagan» belgisi bilan) yoki qat'iy (davomat qabul qilinmaydi).

### Sozlash

1. Virtual muhitni yoqing (`venv\Scripts\activate`) va `install_face_windows.bat` ni ishga tushiring.
   U **tayyor `dlib-bin` paketini** o'rnatadi, shuning uchun Visual Studio yoki CMake **kerak emas**
   (Python 3.10–3.13, Windows 64-bit uchun tayyor paket bor). Qo'lda:
   ```
   pip install dlib-bin face_recognition_models click "setuptools<81"
   pip install face_recognition --no-deps
   ```
2. Shifrlash kalitini yarating va `.env` ga yozing:
   ```
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   ```
   FACE_ENCRYPTION_KEY=<chiqqan kalit>
   FACE_VERIFICATION_ENABLED=True
   FACE_MATCH_TOLERANCE=0.5
   ```
   **Kalitni yo'qotmang va o'zgartirmang:** aks holda barcha yuzlarni qayta ro'yxatdan o'tkazish kerak bo'ladi.
3. Serverni qayta ishga tushiring. **Sozlamalar** sahifasida «Yuz verifikatsiyasi: sozlangan va ishlayapti» chiqishi kerak.
4. **Xodimlar → «Yuz»** tugmasi orqali har bir xodimning yuzini kamera bilan ro'yxatdan o'tkazing
   (yaxshi yoritilgan joyda, kadrda faqat xodim). Ro'yxatdan o'tkazilmagan xodim uchun yuz yo'li ishlamaydi.

Rasm saqlanmaydi: faqat 128 sondan iborat shablon Fernet bilan shifrlanib bazaga yoziladi.
`FACE_MATCH_TOLERANCE` kichraytirilsa tekshiruv qattiqlashadi (begona odamni qabul qilish kamayadi, o'z xodimini rad
etish ko'payadi). Sifat haqida: bir odamning o'zgargan o'lcham/yorug'lik/siqishdagi rasmlari orasidagi masofa
sinovda ~0.1 chiqdi (chegara 0.5), ammo **turli odamlar orasidagi haqiqiy mos kelmaslik sizning xodimlaringiz bilan
sinab ko'rilishi kerak** (bir nechta xodim bilan, turli yorug'likda).

## 5. Xavfsizlik va cheklovlar (ochiq aytilgan)

- **Vaqt faqat server soatidan olinadi**; brauzer yuborgan vaqt e'tiborga olinmaydi.
- **Radius serverda tekshiriladi.** Ammo **GPS soxtalashtirilishi mumkin** (maxsus ilovalar, rootlangan telefon,
  brauzer dasturchi vositalari). Tizim buni to'liq to'sa olmaydi: GPS aniqligi chegarasi va yuz tekshiruvi xavfni
  kamaytiradi, lekin yo'qotmaydi.
- **Jonlilik (liveness) tekshiruvi yo'q:** xodim kameraga boshqa odamning yoki o'z rasmini ko'rsatib aldashi mumkin.
  Jiddiy himoya kerak bo'lsa, alohida liveness xizmati qo'shiladi.
- **«Yuz YOKI joylashuv» usulida** tizim ikki yo'ldan birini talab qiladi: soxta GPS bilan klinika radiusiga
  «kirib» yoki yuzni aldab o'tish mumkin bo'lgan zaif tomon ikki marta ko'payadi. Qat'iyroq nazorat kerak bo'lsa «Yuz VA joylashuv» usulini tanlang.
- Joylashuv faqat «Ishga keldim / Ishdan ketdim» bosilgan lahzada olinadi, doimiy kuzatuv yo'q.
- Xodim boshqa xodimning ma'lumotini ko'ra olmaydi: bu **backendda** tekshiriladi (xodim API'larida 403/404).
- Parollar xeshlanadi; CSRF himoyasi, `HttpOnly` sessiya cookie, login urinishlari cheklangan (daqiqasiga 10).
- Muhim amallar (kirish, xodim o'zgarishi, davomat, sozlamalar) `AuditLog` ga yoziladi; parollar jurnalga tushmaydi.
- **Topshiriq fayllari** (`media/` papkasi) ommaviy havola bilan berilmaydi: faqat egasi va administrator
  autentifikatsiyadan o'tib yuklab oladi. Ruxsat etilgan turlar: pdf, doc(x), xls(x), png, jpg, txt, zip; 10 MB gacha.
  Fayl mazmuni virusga tekshirilmaydi.
- «Muddati o'tgan» holati bazada saqlanmaydi, har safar muddatdan hisoblanadi. Hisobotdagi «Kelmadi» ham shunday
  hisoblanadi (ish kuni bo'lgan, yozuvi yo'q, bugundan oldingi kunlar; xodim tizimga qo'shilgan sanadan boshlab).
  Hisobot davri 93 kundan oshmasligi kerak.
- PDF kirill/lotin harflari uchun Windows'da Arial, Linux'da DejaVu shriftini ishlatadi.
- **Smenalar.** Sozlamalar → Ish jadvallari bo'limida istalgancha smena yaratiladi va xodimga biriktiriladi:
  oddiy (09:00–18:00), ertalabki, kechki, **tungi** (tugash vaqti boshlanishdan kichik, masalan 22:00–06:00) va
  **sutkalik** (boshlanish = tugash, masalan 08:00–08:00, to'liq 24 soat). Davomat sanasi — smena **boshlangan** kun;
  chiqish ertasi kuni qayd etilsa ham o'sha yozuvga yoziladi. `python manage.py seed_initial` tayyor smena
  namunalarini qo'shadi (mavjudlariga tegmaydi). Bir xodimda bir vaqtda bitta smena jadvali bo'ladi;
  haftada turli smenalar (masalan, bu hafta kunduzgi, keyingi hafta tungi) uchun xodimning jadvalini almashtiring.
  Tungi/sutkalik smenada chiqishni unutgan xodim keyingi smenaga baribir kira oladi, lekin 36 soatdan keyin eski
  yozuvga chiqish qo'yib bo'lmaydi.

## 6. Testlar

```
python manage.py test
```
MySQL'siz tez tekshirish uchun: `python manage.py test --settings=config.settings_test` (xotiradagi SQLite).

## 7. Loyiha tuzilmasi

```
config/        sozlamalar, URL, bosh sahifa view'si
accounts/      login/logout, ruxsatlar, AuditLog
employees/     xodimlar, bo'limlar, ish jadvallari
attendance/    davomat, klinika joylashuvi, yuz moduli (face.py), qoidalar (services.py)
reports/       bosh panel API, seed_initial buyrug'i
tasks/         topshiriqlar (API, fayl yuklash/yuklab olish)
rewards/       bonus va intizomiy yozuvlar
notifications/ bildirishnomalar
media/         topshiriq fayllari (ommaviy emas, faqat API orqali beriladi; zaxira nusxaga qo'shing)
templates/index.html   sahifa qobig'i (CDN yo'q: hamma narsa serverning o'zidan beriladi)
frontend/src/app.jsx   React ilovasi (MANBA KOD)
frontend/              yig'ish (build) vositalari; natija static/dist va static/vendor ga yoziladi
static/pwa/            ikonlar, service worker, oflayn sahifa (PWA / Android)
android/, ANDROID.md   Google Play (TWA) uchun yo'riqnoma va namuna sozlama
docs/original_index.html   asl fayl nusxasi
```

## 7a. Frontendni o'zgartirsangiz
Oddiy ishlatishda Node **kerak emas**: yig'ilgan fayllar (`static/dist`, `static/vendor`) loyiha ichida tayyor.
`frontend/src/app.jsx` ni tahrirlasangiz, qayta yig'ing (Node.js 18+ kerak):
```
cd frontend
npm install
npm run build
```

## 7b. Android ilova (Google Play)
Sayt PWA sifatida ham o'rnatiladi (Chrome → «Bosh ekranga qo'shish»), Play Market uchun esa TWA ilova yig'iladi.
To'liq qadamlar: **ANDROID.md**. Maxfiylik siyosati sahifasi: `/privacy/` (matnni yurist bilan ko'rib chiqing).

## 8. Serverga joylashtirish (qisqacha)

`.env` da: `DJANGO_DEBUG=False`, haqiqiy `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_SECURE_COOKIES=True`,
`CSRF_TRUSTED_ORIGINS=https://sizning-domen`. So'ng `python manage.py collectstatic`, WSGI serverda
(masalan, Windows'da `waitress`) ishga tushirish va oldiga HTTPS beradigan proksi (Nginx/Caddy/IIS).
Proksi `X-Forwarded-Proto` va `X-Forwarded-For` sarlavhalarini to'g'ri uzatishi shart.

## Rollar va ruxsatlar (menyularni boshqarish)

Administrator xodimni qo'shayotganda yoki tahrirlayotganda **Rol** va **Tizimdagi huquqlari** bo'limida shu xodim nimalarni ko'rishi va bajarishini belgilaydi:

- **Administrator** — hamma menyu va barcha amallar.
- **Xodim** — o'zining topshiriq, davomat, bonus va jarimalarini doim ko'radi. Qo'shimcha ruxsatlar katakchalar orqali beriladi (yoki tayyor shablon: Bo'lim boshlig'i, Menejer, Kadrlar bo'limi, Buxgalter).

| Bo'lim | Ko'rish | Boshqarish |
|---|---|---|
| Boshqaruv paneli | `dashboard.view` | — |
| Xodimlar | `employees.view` | `employees.manage` (qo'shish, tahrirlash, yuz) |
| Davomat (hammaning) | `attendance.view` | — |
| Topshiriqlar | `tasks.view` | `tasks.manage` (berish, tasdiqlash, o'chirish) |
| Bonus | `bonuses.view` | `bonuses.manage` |
| Ogohlantirish/Jarima | `discipline.view` | `discipline.manage` |
| Hisobotlar | `reports.view` | — |
| Sozlamalar (joylashuv, bo'lim, jadval) | — | `settings.manage` |

Qoidalar: «boshqarish» avtomatik «ko'rish»ni ham beradi; ruxsatlar tekshiruvi backendda (menyu yashirilishi faqat qulaylik uchun); rol va ruxsatlarni faqat administrator o'zgartiradi, `employees.manage` egasi administratorni yoki o'zidan yuqori huquqli xodimni o'zgartira olmaydi; administrator o'zini pastga tushira olmaydi. Ruxsatlar o'zgarishi audit jurnaliga yoziladi. Yangi menyular xodimning chap menyusida «Boshqaruv» bo'limida chiqadi. Eski bazalar uchun `python manage.py migrate` kerak (0004).


## Bazani PostgreSQL'dan MySQL'ga ko'chirish (eski ma'lumotlar bo'lsa)
Eski (PostgreSQL) sozlamasi bilan ishlayotgan nusxada: `python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.permission --indent 1 -o data.json`.
Keyin yangi (MySQL) sozlamasida: `python manage.py migrate`, so'ng `python manage.py loaddata data.json`. Yuz ma'lumotlari shifrlangani uchun
`FACE_ENCRYPTION_KEY` ni o'zgartirmang. Yangi o'rnatishda (ma'lumot yo'q) bu qadam kerak emas.

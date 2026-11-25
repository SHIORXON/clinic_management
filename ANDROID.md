# Android ilova (Google Play) — qadamlar

Ilova **Trusted Web Activity (TWA)**: Play Market'dagi ilova — sizning HTTPS saytingizni to'liq ekranda ochuvchi
"o'ram". Alohida Android kodi yo'q: sayt yangilansa, ilova ham yangilanadi (qayta yuklash shart emas).

> Men (Claude) bu muhitda Android SDK yuklab ola olmadim, shuning uchun **yakuniy `.aab` faylni siz o'z
> kompyuteringizda yig'asiz**. Loyiha buning uchun tayyor (PWA, ikonlar, `assetlinks.json`, maxfiylik sahifasi).
> Men Play Market'da ilovani nashr qila olmayman va uni telefonda sinab ko'rmadim.

## 0. Avval nima kerak
1. **Serverda ishlayotgan sayt, haqiqiy domen va HTTPS** (README, 8-bo'lim). Localhost/ngrok bilan Play'ga chiqib bo'lmaydi.
2. **Google Play Console hisobi** (bir martalik to'lov, taxminan 25 USD). Shaxsiy hisob bo'lsa, Google hozirgi paytda
   ommaga chiqarishdan oldin yopiq sinov (bir necha tester, 14 kun) talab qilishi mumkin: shartlarni Play Console'da tekshiring.
3. Kompyuterda **Node.js 18+** (https://nodejs.org). JDK va Android SDK ni Bubblewrap o'zi yuklab beradi (so'rasa «Y» deng).

## 1. Saytni tekshiring
Brauzerda oching: `https://DOMEN/manifest.webmanifest` (JSON chiqishi kerak) va `https://DOMEN/privacy/` (maxfiylik siyosati).
Chrome → DevTools → Application → Manifest bo'limida xato bo'lmasligi kerak.

## 2. Ilovani yig'ish (Bubblewrap)
```
npm install -g @bubblewrap/cli
mkdir goldmed-android && cd goldmed-android
bubblewrap init --manifest=https://DOMEN/manifest.webmanifest
```
Savollar (muhimlari):
- **Application ID (package)**: masalan `uz.klinikanomi.goldmed`. Bir marta tanlanadi, keyin **o'zgartirib bo'lmaydi**.
- **Request user to grant location permission?** → **Yes** (davomat joylashuv bilan ishlaydi; shusiz TWA ichida GPS ishlamasligi mumkin).
- **Notifications** → No (hozircha push yo'q).
- **Key store**: yangi yaratiladi (`goldmed.keystore`). **Parolni va shu faylni yo'qotmang va hech kimga bermang**: yo'qolsa, ilovani
  keyin yangilab bo'lmaydi. Zaxira nusxasini xavfsiz joyga saqlang.

(`android/twa-manifest.json` — javoblar uchun namuna.) So'ng:
```
bubblewrap build
```
Natija: `app-release-bundle.aab` (Play'ga yuklanadi) va `app-release-signed.apk` (telefonga o'rnatib sinash uchun).

## 3. Digital Asset Links (ilova tepasidagi brauzer panelini yo'qotadi)
```
bubblewrap fingerprint
```
`SHA256` barmoq izini nusxalang. Serverdagi `.env` ga yozing va serverni qayta ishga tushiring:
```
ANDROID_PACKAGE_NAME=uz.klinikanomi.goldmed
ANDROID_SHA256_FINGERPRINTS=AA:BB:...:ZZ
```
Tekshiring: `https://DOMEN/.well-known/assetlinks.json` ichida paket nomi va barmoq iz ko'rinsin.
**Muhim:** Play Console'ga yuklaganingizdan keyin Google ilovani o'z kalit bilan qayta imzolaydi (Play App Signing). Console →
Setup → App signing bo'limidagi **App signing key certificate SHA-256** ni ham `ANDROID_SHA256_FINGERPRINTS` ga vergul bilan qo'shing.

## 4. Telefonda sinash
APK ni telefonga o'rnating. Tekshiring: kirish, **kamera** (yuz), **joylashuv**, davomat, topshiriq faylini yuklash.
Tepada manzil paneli ko'rinsa, 3-qadam to'g'ri bajarilmagan.

## 5. Play Console
1. Yangi ilova yarating → **AAB** ni «Internal testing»ga yuklang, keyin yopiq/ochiq sinov va ishlab chiqarishga.
2. **Maxfiylik siyosati URL**: `https://DOMEN/privacy/` (avval u yerdagi matnni klinika ma'lumotlari bilan to'ldiring, 6-qadam).
3. **Data safety** shakli: yig'iladigan ma'lumotlar — *taxminiy/aniq joylashuv*, *rasm (yuz, kamera orqali; saqlanmaydi, faqat shifrlangan
   yuz izi)*, *ism, telefon, lavozim*. Ma'lumot uzatilishi shifrlangan (HTTPS).
4. **Ruxsatlar deklaratsiyasi**: joylashuv — «xodim davomatini klinika hududida tasdiqlash».
5. **App access**: Google tekshiruvchilarga kirish kerak bo'ladi. Alohida **sinov xodimi hisobi** (login/parol) yarating va shu yerga yozing.
6. **Kontent reytingi**, **maqsadli auditoriya** (kattalar), **ilova toifasi** (Business/Productivity) ni to'ldiring.
7. Do'kon ikonkasi: `static/pwa/play-store-icon-512.png` (vaqtinchalik; o'zingizning logotipingizga almashtirish yaxshi). Skrinshotlar kerak (telefon).

## 6. Maxfiylik va qonun
- Yuz va joylashuv — **shaxsiy/biometrik ma'lumot**. Xodimlardan **yozma rozilik** oling va maxfiylik siyosatini ularga ko'rsating.
  O'zbekiston qonunchiligi bo'yicha aniq talablarni yurist bilan tekshiring (men yurist emasman).
- `/privacy/` sahifasi — **namuna**. `.env` da `CLINIC_NAME` va `PRIVACY_CONTACT` ni to'ldiring va matnni yurist bilan ko'rib chiqing.

## 7. Yangilash
- Sayt (Django/frontend) o'zgarsa: faqat serverni yangilang, ilovani qayta yuklash **shart emas**.
- Ilova ichidagi sozlama o'zgarsa (ikonka, nom, package): `appVersion` ni oshirib, `bubblewrap build` va yangi AAB yuklang.

## Cheklovlar
- Internet shart (davomat serverda). Oflayn bo'lsa, «Internetga ulanib bo'lmadi» sahifasi chiqadi.
- iPhone (App Store) uchun bu yo'l ishlamaydi; u alohida ish. Hozircha iPhone'da sayt «Bosh ekranga qo'shish» orqali ishlaydi.
- Ilovaning ishlashi Chrome (yoki Android'dagi standart brauzer) yangi bo'lishiga bog'liq.

## Sizning sozlamangiz: clinic-system.uz
- Domen: `clinic-system.uz`, paket nomi: `uz.clinicsystem.goldmed` (`android/twa-manifest.json` shu bilan to'ldirilgan).
- Kompyuteringizda `android/build_android.bat` ni ikki marta bosing: u Bubblewrap'ni o'rnatadi, ilovani yig'adi va barmoq izini chiqaradi.
- Serverdagi `.env` ga qo'shing (so'ng serverni qayta yoqing):
```
DJANGO_ALLOWED_HOSTS=clinic-system.uz,www.clinic-system.uz
CSRF_TRUSTED_ORIGINS=https://clinic-system.uz,https://www.clinic-system.uz
DJANGO_SECURE_COOKIES=True
ANDROID_PACKAGE_NAME=uz.clinicsystem.goldmed
ANDROID_SHA256_FINGERPRINTS=<bubblewrap fingerprint natijasi>
```

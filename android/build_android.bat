@echo off
chcp 65001 >nul
REM Gold Med Android ilovasini yig'ish (Windows). Node.js 18+ kerak: https://nodejs.org
REM Domen: clinic-system.uz  |  Paket: uz.clinicsystem.goldmed
where node >nul 2>nul || (echo Node.js topilmadi. https://nodejs.org dan o'rnating. & pause & exit /b 1)
call npm install -g @bubblewrap/cli
if not exist goldmed-android mkdir goldmed-android
cd goldmed-android
echo.
echo === 1/3: init. Savollarda: Application ID = uz.clinicsystem.goldmed, "location permission" = Yes, Notifications = No.
echo === JDK/Android SDK yuklashni so'rasa Y deng. Keystore parolini YOZIB QO'YING va yo'qotmang!
call bubblewrap init --manifest=https://clinic-system.uz/manifest.webmanifest
echo.
echo === 2/3: build
call bubblewrap build
echo.
echo === 3/3: SHA256 barmoq izi (serverdagi .env ga ANDROID_SHA256_FINGERPRINTS sifatida yozing)
call bubblewrap fingerprint
echo.
echo Tayyor: app-release-signed.apk (telefonga o'rnatish), app-release-bundle.aab (Play Market).
pause

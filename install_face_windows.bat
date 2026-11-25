@echo off
REM Yuz verifikatsiyasi kutubxonalarini o'rnatadi (kompilyator kerak emas: tayyor dlib-bin paketi ishlatiladi).
REM Avval virtual muhitni yoqing:  venv\Scripts\activate   so'ng shu faylni ishga tushiring.
echo.
echo [1/3] dlib-bin va yordamchi paketlar o'rnatilmoqda...
pip install dlib-bin face_recognition_models click "setuptools<81"
if errorlevel 1 goto fail

echo.
echo [2/3] face_recognition o'rnatilmoqda...
REM --no-deps muhim: face_recognition "dlib" ni manba kodidan kompilyatsiya qilishga urinmasligi uchun
pip install face_recognition --no-deps
if errorlevel 1 goto fail

echo.
echo [3/3] Tekshirilmoqda...
python -c "import face_recognition, dlib; print('OK: face_recognition ishlayapti, dlib', dlib.__version__)"
if errorlevel 1 goto fail

echo.
echo Tayyor. Endi .env faylida FACE_VERIFICATION_ENABLED=True va FACE_ENCRYPTION_KEY ni sozlang (README, 4-bo'lim).
goto end

:fail
echo.
echo XATO: o'rnatish muvaffaqiyatsiz tugadi. Yuqoridagi xato matnini nusxalab yuboring.

:end
pause

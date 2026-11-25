@echo off
REM Tizimni shu kompyuterda ishga tushiradi va brauzerda ochadi. Loyiha papkasidagi shu faylni ikki marta bosing.
cd /d "%~dp0"
if not exist venv\Scripts\activate.bat (
  echo XATO: venv topilmadi. Avval README 1-bo'limdagi o'rnatishni bajaring.
  pause
  exit /b 1
)
call venv\Scripts\activate.bat
python manage.py migrate
if errorlevel 1 (
  echo.
  echo XATO: baza yangilanmadi. MySQL xizmati yoqilganini va .env dagi parolni tekshiring.
  pause
  exit /b 1
)
start "" http://127.0.0.1:8000
echo.
echo Tizim ishlayapti: http://127.0.0.1:8000   (to'xtatish uchun bu oynani yoping yoki Ctrl+C)
python manage.py runserver 127.0.0.1:8000
pause

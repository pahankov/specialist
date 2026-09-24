@echo off
setlocal EnableDelayedExpansion

echo.
echo ========================================
echo   Online Booking — Запуск
echo ========================================
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%online-booking\backend"
set "FRONTEND_DIR=%PROJECT_DIR%online-booking\frontend"

:: ─── Проверка зависимостей ─────────────────────────────────────
py --version >nul 2>&1 || (echo [ERROR] Python не найден && pause && exit /b 1)
node --version >nul 2>&1 || (echo [ERROR] Node.js не найден && pause && exit /b 1)

:: ─── Убиваем старые процессы ─────────────────────────────────────
echo [1/5] Освобождаем порты...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " 2^>nul') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 " 2^>nul') do taskkill /F /PID %%a 2>nul
timeout /t 1 /nobreak >nul

:: ─── Бэкап БД перед запуском ─────────────────────────────────────
echo [2/5] Бэкап БД...
if exist "%BACKEND_DIR%\online_booking.db" (
    call "%BACKEND_DIR%\venv\Scripts\python.exe" "%BACKEND_DIR%\backup_db.py" >nul 2>&1
)

:: ─── Запуск бэкенда в фоновой консоли ───────────────────────────
echo [3/5] Запускаю бэкенд (port 8000)...
start "OB-Backend" /min cmd /k "cd /d %BACKEND_DIR% && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

:: ─── Health-check бэкенда ────────────────────────────────────────
echo [4/5] Ожидание бэкенда...
set /a retries=0
:wait_backend
timeout /t 1 /nobreak >nul
curl -s http://localhost:8000/docs >nul 2>&1
if !errorlevel! equ 0 (
    echo       ✓ Бэкенд готов
) else (
    set /a retries+=1
    if !retries! lss 15 goto wait_backend
    echo       [WARN] Бэкенд не запустился за 15 секунд
)

:: ─── Запуск фронтенда в фоновой консоли ─────────────────────────
echo [5/5] Запускаю фронтенд (port 3000)...
start "OB-Frontend" /min cmd /k "cd /d %FRONTEND_DIR% && npx vite --host 0.0.0.0 --port 3000"

echo.
echo ========================================
echo   ✓ Готово!
echo   Бэкенд:  http://localhost:8000
echo   Фронтенд: http://localhost:3000
echo ========================================
echo.
echo Консоли бэкенда и фронтенда свёрнуты.
echo Чтобы остановить — закройте их из панели задач.
echo.
pause

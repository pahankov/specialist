@echo off
echo === Запуск Online Booking ===
echo.

set "PROJECT_DIR=%~dp0"
set "BACKEND_DIR=%PROJECT_DIR%backend"
set "FRONTEND_DIR=%PROJECT_DIR%frontend"

echo Убиваем старые процессы...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul

echo Очищаем кэш Vite...
if exist "%FRONTEND_DIR%\node_modules\.vite" rmdir /s /q "%FRONTEND_DIR%\node_modules\.vite" 2>nul

echo Запуск бэкенда (порт 8000)...
start "Online Booking - Backend" cmd /k "cd /d %BACKEND_DIR% && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo Запуск фронтенда (порт 3000)...
start "Online Booking - Frontend" cmd /k "cd /d %FRONTEND_DIR% && npx.cmd vite --host 0.0.0.0 --port 3000"

echo.
echo Готово!
echo   Бэкенд:  http://localhost:8000
echo   Фронтенд: http://localhost:3000
echo.
echo Окна не закрывай!
pause

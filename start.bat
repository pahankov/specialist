@echo off
echo === Запуск Sugar Booking ===
echo.

REM Автоопределение worktree или корневого каталога
set "PROJECT_DIR=%~dp0"
set "WORKTREE_DIR=%PROJECT_DIR%.gigacode_vsc\worktrees\open-brick"

if exist "%WORKTREE_DIR%\frontend\" (
    echo Using worktree: %WORKTREE_DIR%
    set "BACKEND_DIR=%WORKTREE_DIR%\backend"
    set "FRONTEND_DIR=%WORKTREE_DIR%\frontend"
) else (
    echo Using main project
    set "BACKEND_DIR=%PROJECT_DIR%backend"
    set "FRONTEND_DIR=%PROJECT_DIR%frontend"
)

echo Убиваем старые процессы...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 "') do taskkill /F /PID %%a 2>nul
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 "') do taskkill /F /PID %%a 2>nul
timeout /t 2 /nobreak >nul

echo Запуск бэкенда (порт 8000)...
start "Sugar Booking - Backend" cmd /k "cd /d %BACKEND_DIR% && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo Запуск фронтенда (порт 3000)...
start "Sugar Booking - Frontend" cmd /k "cd /d %FRONTEND_DIR% && npx.cmd vite --host 0.0.0.0 --port 3000"

echo.
echo Готово!
echo   Бэкенд:  http://localhost:8000
echo   Фронтенд: http://localhost:3000
echo.
echo Окна не закрывай!
pause

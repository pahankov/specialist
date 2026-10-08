@echo off
echo ========================================
echo   Setup Automatic Prod -^> Local Sync
echo ========================================
echo.
echo Runs pull_production.py every N minutes via Windows Task Scheduler.
echo Credentials are read from backend\.env (gitignored, never commit!).
echo Usage: setup_auto_sync.bat [minutes, default 30]
echo.

set "MINUTES=%~1"
if "%MINUTES%"=="" set "MINUTES=30"

set "WRAPPER=%~dp0sync_production.bat"
set "TASK_NAME=BeautySpecialist_Sync"

echo Creating scheduled task (every %MINUTES% min, for 365 days)...
REM NOTE: Task Scheduler rejects infinite repetition ([TimeSpan]::MaxValue),
REM so the trigger lives 365 days — rerun this setup once a year.
powershell -Command ^
    "$action = New-ScheduledTaskAction -Execute '%WRAPPER%';" ^
    "$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes %MINUTES%) -RepetitionDuration (New-TimeSpan -Days 365);" ^
    "Register-ScheduledTask -TaskName '%TASK_NAME%' -Action $action -Trigger $trigger -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable) -RunLevel Limited -User (whoami)"

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! Sync runs every %MINUTES% minutes (for 365 days, then rerun setup).
    echo Log: online-booking\backend\logs\pull_production.log
    echo.
    echo First fill backend\.env with:
    echo   PROD_API=https://beauty-specialist.ru
    echo   PROD_EMAIL=your-admin-email
    echo   PROD_PASSWORD=your-admin-password
    echo.
    echo To remove: run remove_auto_sync.bat
) else (
    echo.
    echo FAILED. Run this script as Administrator.
)

echo.
pause

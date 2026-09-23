@echo off
echo ========================================
echo   Setup Automatic Daily Backup
echo ========================================
echo.
echo This will create a Windows Task that runs backup daily at 3:00 AM.
echo.

set "SCRIPT_PATH=%~dp0backup_db.py"
set "TASK_NAME=BeautySpecialist_Backup"

echo Creating scheduled task...
powershell -Command ^
    "Register-ScheduledTask -TaskName '%TASK_NAME%' -Action (New-ScheduledTaskAction -Execute 'python' -Argument '%SCRIPT_PATH% --compress --keep 30') -Trigger (New-ScheduledTaskTrigger -Daily -At 3AM) -Settings (New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries) -RunLevel Limited -User (whoami)"

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! Automatic backup is configured:
    echo   - Runs daily at 3:00 AM
    echo   - Compresses backups
    echo   - Keeps last 30 days
    echo.
    echo To remove: run remove_backup_task.bat
) else (
    echo.
    echo FAILED. Run this script as Administrator.
)

echo.
pause

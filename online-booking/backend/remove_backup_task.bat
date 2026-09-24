@echo off
echo ========================================
echo   Remove Automatic Backup
echo ========================================
echo.

set "TASK_NAME=BeautySpecialist_Backup"

echo Removing scheduled task...
schtasks /Delete /TN "%TASK_NAME%" /F

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! Automatic backup removed.
) else (
    echo.
    echo Task not found or permission denied.
)

echo.
pause

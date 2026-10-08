@echo off
echo ========================================
echo   Remove Automatic Prod -^> Local Sync
echo ========================================
echo.

set "TASK_NAME=BeautySpecialist_Sync"

echo Removing scheduled task...
schtasks /Delete /TN "%TASK_NAME%" /F

if %errorlevel% equ 0 (
    echo.
    echo SUCCESS! Automatic sync removed.
) else (
    echo.
    echo Task not found or permission denied.
)

echo.
pause

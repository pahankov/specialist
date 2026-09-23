@echo off
echo ========================================
echo   Restore Database
echo ========================================
echo.

cd /d "%~dp0"

echo Available backups:
echo.
python restore_db.py --list
echo.

set /p BACKUP="Enter backup filename (or 'latest'): "

if "%BACKUP%"=="latest" (
    python restore_db.py latest
) else (
    python restore_db.py "%BACKUP%"
)

echo.
echo Done.
pause

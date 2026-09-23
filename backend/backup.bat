@echo off
echo ========================================
echo   Backup Database
echo ========================================
echo.

cd /d "%~dp0"

python backup_db.py --compress

echo.
echo Done. Backups stored in: backups\
echo.
pause

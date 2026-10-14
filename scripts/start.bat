@echo off
rem Launcher for scripts/start.ps1. Keeps the window open so errors are visible.
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
echo.
echo [start.bat] Exit code: %ERRORLEVEL%
pause

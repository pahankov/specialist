@echo off
rem Launcher for scripts/start.ps1. Keeps the window open so errors are visible.
rem Full powershell.exe path: bare "powershell" may be missing from PATH (exit 9009).
cd /d "%~dp0.."
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
echo.
echo [start.bat] Exit code: %ERRORLEVEL%
pause

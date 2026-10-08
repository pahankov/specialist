@echo off
REM Pull production data into local DB (unattended).
REM Credentials come from backend\.env (gitignored): PROD_EMAIL/PROD_PASSWORD.
REM Log: backend\logs\pull_production.log
cd /d "%~dp0"

if not exist "logs" mkdir logs

call venv\Scripts\python.exe pull_production.py --yes --quiet >> "logs\pull_production.log" 2>&1

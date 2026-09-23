@echo off
REM Автоопределение worktree или корневого каталога
set "PROJECT_DIR=%~dp0"
set "WORKTREE_DIR=%PROJECT_DIR%.gigacode_vsc\worktrees\open-brick"

if exist "%WORKTREE_DIR%\backend\" (
    echo Using worktree: %WORKTREE_DIR%
    cd "%WORKTREE_DIR%\backend"
) else (
    echo Using main project
    cd "%PROJECT_DIR%backend"
)

call .\venv\Scripts\activate.bat
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause

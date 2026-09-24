@echo off
REM Автоопределение worktree или корневого каталога
set "PROJECT_DIR=%~dp0"
set "WORKTREE_DIR=%PROJECT_DIR%.gigacode_vsc\worktrees\open-brick"

if exist "%WORKTREE_DIR%\online-booking\frontend\" (
    echo Using worktree: %WORKTREE_DIR%
    cd "%WORKTREE_DIR%\online-booking\frontend"
) else (
    echo Using main project
    cd "%PROJECT_DIR%online-booking\frontend"
)

npm run dev

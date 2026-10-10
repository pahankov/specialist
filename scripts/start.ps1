# Online Booking - Start (backend + frontend, main project only).
# For GigaCode worktrees use run_backend.bat / run_frontend.bat (they auto-detect worktree).
# NOTE: this file is pure ASCII on purpose - powershell.exe 5.1 reads
# BOM-less scripts as ANSI, and any multibyte char breaks parsing.
$ErrorActionPreference = "Stop"
# Script lives in scripts/ - repo root is one level up.
$ProjectDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$BackendDir = Join-Path $ProjectDir "online-booking\backend"
$FrontendDir = Join-Path $ProjectDir "online-booking\frontend"

$TotalSteps = 8
$StartedAt = Get-Date

function Write-Banner {
    param([string]$Title)
    Write-Host ""
    Write-Host "  +========================================+" -ForegroundColor Cyan
    Write-Host "  |  $Title" -ForegroundColor Cyan
    Write-Host "  +========================================+" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Step {
    param([int]$Num, [string]$Title)
    Write-Host "  [$Num/$TotalSteps] $Title..." -ForegroundColor Yellow
}

function Write-Ok {
    param([string]$Message = "OK")
    Write-Host "    [OK] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "    [WARN] $Message" -ForegroundColor DarkYellow
}

function Write-Skip {
    param([string]$Message)
    Write-Host "    [SKIP] $Message" -ForegroundColor Gray
}

function Write-Fail {
    param([string]$Message)
    Write-Host "    [FAIL] $Message" -ForegroundColor Red
}

Write-Banner "Online Booking - Start"

# --- Clean compiled JS files ---
Write-Step 0 "Cleaning compiled files"
$JsFiles = Get-ChildItem -Path "$FrontendDir\src" -Recurse -Filter "*.js" -File -ErrorAction SilentlyContinue
if ($JsFiles) {
    $JsFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Ok "Removed $($JsFiles.Count) .js files from src/"
}
if (Test-Path "$FrontendDir\node_modules\.vite") {
    Remove-Item -Recurse -Force "$FrontendDir\node_modules\.vite" -ErrorAction SilentlyContinue
    Write-Ok "Removed Vite cache"
}
Write-Ok "Clean"

# --- Check dependencies ---
Write-Step 1 "Checking dependencies"
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Fail "Python not found"
    pause; exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Fail "Node.js not found"
    pause; exit 1
}
Write-Ok "python + node present"

# --- Free ports ---
Write-Step 2 "Freeing ports 8000/3000"
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1
Write-Ok "Ports free"

# --- Backup DB ---
Write-Step 3 "Backup DB"
$DbFile = Join-Path $BackendDir "online_booking.db"
if (Test-Path $DbFile) {
    $PyExe = Join-Path $BackendDir "venv\Scripts\python.exe"
    if (Test-Path $PyExe) { & $PyExe (Join-Path $BackendDir "backup_db.py") 2>$null }
}
Write-Ok "Backup done"

# --- Sync production DB ---
# Pulls prod masters/clients/schedule into local DB (creds from backend/.env).
# Best-effort: never blocks startup (offline/prod down => warning only).
Write-Step 4 "Syncing production DB"
$PyExe = Join-Path $BackendDir "venv\Scripts\python.exe"
if (Test-Path $PyExe) {
    try {
        & $PyExe (Join-Path $BackendDir "pull_production.py") --yes --quiet --db (Join-Path $BackendDir "online_booking.db")
        if ($LASTEXITCODE -eq 0) { Write-Ok "Synced with production" }
        else { Write-Warn "Sync failed (exit $LASTEXITCODE), continuing with local DB" }
    } catch {
        Write-Warn "Sync failed, continuing with local DB"
    }
} else {
    Write-Skip "No venv python"
}

# --- Start backend ---
Write-Step 5 "Starting backend (port 8000)"
Start-Process "cmd.exe" -ArgumentList "/k", "cd /d `"$BackendDir`" && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized -WorkingDirectory $BackendDir
Write-Ok "Backend console launched (minimized)"

# --- Health-check ---
Write-Step 6 "Waiting for backend"
$BackendReady = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        Invoke-WebRequest -Uri "http://localhost:8000/docs" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop | Out-Null
        $BackendReady = $true
        break
    } catch {}
}
if ($BackendReady) { Write-Ok "Backend ready" }
else { Write-Warn "Backend not responding yet - check its console" }

# --- Start frontend ---
Write-Step 7 "Starting frontend (port 3000)"
Start-Process "cmd.exe" -ArgumentList "/k", "cd /d `"$FrontendDir`" && npx vite --host 0.0.0.0 --port 3000" -WindowStyle Minimized -WorkingDirectory $FrontendDir
Write-Ok "Frontend console launched (minimized)"

# --- Done ---
$Elapsed = [math]::Round(((Get-Date) - $StartedAt).TotalSeconds, 1)
Write-Host ""
Write-Host "  +========================================+" -ForegroundColor Green
Write-Host "  |  Done in ${Elapsed}s!" -ForegroundColor Green
Write-Host "  |" -ForegroundColor Green
Write-Host "  |  Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "  |  Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "  +========================================+" -ForegroundColor Green
Write-Host ""
Write-Host "  Consoles minimized. To stop - close them from taskbar." -ForegroundColor Gray
Write-Host ""
Write-Host "  Press Enter to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

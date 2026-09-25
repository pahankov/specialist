# Online Booking — Start
$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectDir "online-booking\backend"
$FrontendDir = Join-Path $ProjectDir "online-booking\frontend"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Online Booking — Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# ─── Clean compiled JS files ─────────────────────────────────────
Write-Host "[0/7] Cleaning compiled files..." -ForegroundColor Yellow
$JsFiles = Get-ChildItem -Path "$FrontendDir\src" -Recurse -Filter "*.js" -File -ErrorAction SilentlyContinue
if ($JsFiles) {
    $JsFiles | Remove-Item -Force -ErrorAction SilentlyContinue
    Write-Host "  Removed $($JsFiles.Count) .js files from src/" -ForegroundColor Yellow
}
if (Test-Path "$FrontendDir\node_modules\.vite") {
    Remove-Item -Recurse -Force "$FrontendDir\node_modules\.vite" -ErrorAction SilentlyContinue
    Write-Host "  Removed Vite cache" -ForegroundColor Yellow
}
Write-Host "  OK" -ForegroundColor Green

# ─── Check dependencies ──────────────────────────────────────────
Write-Host "[1/7] Checking dependencies..." -ForegroundColor Yellow
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python not found" -ForegroundColor Red
    pause; exit 1
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Node.js not found" -ForegroundColor Red
    pause; exit 1
}
Write-Host "  OK" -ForegroundColor Green

# ─── Free ports ──────────────────────────────────────────────────
Write-Host "[2/7] Freeing ports..." -ForegroundColor Yellow
Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-NetTCPConnection -LocalPort 3000 -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 1

# ─── Backup DB ───────────────────────────────────────────────────
Write-Host "[3/7] Backup DB..." -ForegroundColor Yellow
$DbFile = Join-Path $BackendDir "online_booking.db"
if (Test-Path $DbFile) {
    $PyExe = Join-Path $BackendDir "venv\Scripts\python.exe"
    if (Test-Path $PyExe) { & $PyExe (Join-Path $BackendDir "backup_db.py") 2>$null }
}
Write-Host "  OK" -ForegroundColor Green

# ─── Start backend ───────────────────────────────────────────────
Write-Host "[4/7] Starting backend (port 8000)..." -ForegroundColor Yellow
Start-Process "cmd.exe" -ArgumentList "/k", "cd /d `"$BackendDir`" && call venv\Scripts\activate.bat && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000" -WindowStyle Minimized -WorkingDirectory $BackendDir

# ─── Health-check ────────────────────────────────────────────────
Write-Host "[5/7] Waiting for backend..." -ForegroundColor Yellow
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    try {
        Invoke-WebRequest -Uri "http://localhost:8000/docs" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop | Out-Null
        Write-Host "  OK Backend ready" -ForegroundColor Green
        break
    } catch {}
}

# ─── Start frontend ──────────────────────────────────────────────
Write-Host "[6/7] Starting frontend (port 3000)..." -ForegroundColor Yellow
Start-Process "cmd.exe" -ArgumentList "/k", "cd /d `"$FrontendDir`" && npx vite --host 0.0.0.0 --port 3000" -WindowStyle Minimized -WorkingDirectory $FrontendDir

# ─── Done ────────────────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   OK Done!" -ForegroundColor Green
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   Frontend: http://localhost:3000" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Consoles minimized. To stop - close them from taskbar." -ForegroundColor Gray
Write-Host ""
Write-Host "Press Enter to exit..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

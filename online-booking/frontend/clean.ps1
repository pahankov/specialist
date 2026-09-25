# Очистка скомпилированных файлов из src/
# Запускать после git reset --hard

Write-Host "Cleaning compiled .js files from src/..." -ForegroundColor Yellow

# Удаляем все .js файлы из src/
Get-ChildItem -Path "src" -Recurse -Filter "*.js" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Удаляем кэш Vite
if (Test-Path "node_modules\.vite") {
    Remove-Item -Recurse -Force "node_modules\.vite" -ErrorAction SilentlyContinue
    Write-Host "  Removed Vite cache" -ForegroundColor Green
}

# Удаляем dist
if (Test-Path "dist") {
    Remove-Item -Recurse -Force "dist" -ErrorAction SilentlyContinue
    Write-Host "  Removed dist/" -ForegroundColor Green
}

Write-Host "  Cleaned!" -ForegroundColor Green
Write-Host ""
Write-Host "Now run: npm run dev" -ForegroundColor Cyan

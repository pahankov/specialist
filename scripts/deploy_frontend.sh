#!/bin/bash
# Frontend stage of the deploy: source check -> clean caches -> npm ci -> build
# -> integrity checks -> copy to the nginx-served directory with verification.
# Called from .github/workflows/deploy.yml with the repo root as $1.
# Mirrors script_stop:true -> set -e. No secrets here (bundle must stay clean).
set -e

ROOT="${1:?usage: bash scripts/deploy_frontend.sh /var/www/beauty-specialist}"
cd "$ROOT/online-booking/frontend"

echo "=== FRONTEND SOURCE CHECK ==="
echo "Current commit:"
git log -1 --oneline
echo "DAData import in LoginModal:"
grep -n "dadata" src/components/LoginModal.tsx || echo "NOT FOUND"
echo "City autocomplete UI in LoginModal:"
grep -n "city-dropdown" src/components/LoginModal.tsx || echo "NOT FOUND"
echo "DAData API file exists:"
ls -la src/api/dadata.ts || echo "NOT FOUND"
echo "=============================="
# Remove stale .js files from src/ — Vite may read them instead of .ts/.tsx
echo "=== REMOVING STALE JS FILES ==="
find src -name "*.js" -type f -delete 2>/dev/null || true
echo "=== CLEANING BUILD CACHE ==="
# Remove ALL possible Vite caches (local + global)
rm -rf node_modules/.vite
rm -rf .vite
rm -rf dist
rm -rf node_modules
rm -rf ~/.cache/vite
rm -rf ~/.vite
rm -rf node_modules/.cache
# Also remove any Vite cache in the project root
rm -rf .vite-temp
rm -rf .vite-deps
npm cache clean --force
echo "=== INSTALLING DEPENDENCIES ==="
npm ci --no-audit --no-fund
echo "=== CLEARING VITE DEPS CACHE (AFTER npm ci) ==="
# Clear Vite's dependency pre-bundling cache AFTER npm ci
rm -rf node_modules/.vite/deps
rm -rf node_modules/.vite/deps-cache
rm -rf node_modules/.vite

# CRITICAL: Clear global Vite cache AGAIN right before build
# npm ci restores node_modules with same hashes, Vite uses global cache
rm -rf ~/.cache/vite
rm -rf ~/.vite/deps
rm -rf node_modules/.vite

# Set BUILD_ID from the currently deployed commit's short SHA
# GITHUB_SHA is not available via SSH — use git instead
export BUILD_ID=$(git rev-parse --short=7 HEAD)
echo "BUILD_ID: $BUILD_ID"

echo "=== BUILDING FRONTEND ==="
npm run build 2>&1 | tee /tmp/build-output.txt
echo "=== BUILD OUTPUT ==="
cat /tmp/build-output.txt

# Verify dist was actually produced
if [ ! -f dist/index.html ]; then
    echo "ERROR: build produced no dist/index.html — aborting"
    exit 1
fi

# Get the JS file hash from built index.html
BUILT_JS=$(grep -o 'assets/[^"]*\.js' dist/index.html | head -1 | sed 's|assets/||')
echo "Built JS file: $BUILT_JS"
echo "✓ Built a new JS file: $BUILT_JS"

# Verify build contains new code (check BUILT JS, not source)
echo "=== VERIFYING BUILD INTEGRITY ==="

# List all JS files in dist/assets
ls -la dist/assets/*.js 2>/dev/null || echo "No JS files found in dist/assets"

# Check that built JS contains DAData (searchCities is a property that survives minification)
if ! grep -q "searchCities" dist/assets/*.js 2>/dev/null; then
    echo "ERROR: Built JS missing searchCities! Build is stale or wrong!"
    exit 1
fi
echo "✓ Built JS contains DAData (searchCities)"

# Check that built JS does NOT call DaData directly (secret/URL must never ship in bundle)
if grep -q "suggestions.dadata.ru" dist/assets/*.js 2>/dev/null; then
    echo "ERROR: Built JS calls DaData directly! Must go via /api/dadata proxy!"
    exit 1
fi
echo "✓ Built JS has no direct DaData calls"

# Check that built JS uses the same-origin proxy path (required since the cities fallback)
# NOTE: /api/v1/cities IS expected in the bundle — local DB fallback in dadata.ts
if ! grep -q "/api/dadata" dist/assets/*.js 2>/dev/null; then
    echo "ERROR: Built JS missing /api/dadata proxy path! Build is stale!"
    exit 1
fi
echo "✓ Built JS uses /api/dadata proxy"

# Copy with overwrite verification - remove entire dist first
echo "=== COPYING FRONTEND TO DEPLOY DIRECTORY ==="
rm -rf /var/www/beauty-specialist/frontend/dist
mkdir -p /var/www/beauty-specialist/frontend/dist
cp -r dist/* /var/www/beauty-specialist/frontend/dist/
echo "Frontend files copied:"
ls -la /var/www/beauty-specialist/frontend/dist/
ls -la /var/www/beauty-specialist/frontend/dist/assets/

# Verify copied JS file matches built JS
COPIED_JS=$(grep -o 'assets/[^"]*\.js' /var/www/beauty-specialist/frontend/dist/index.html | head -1 | sed 's|assets/||')
echo "Copied JS file: $COPIED_JS"
if [ "$BUILT_JS" != "$COPIED_JS" ]; then
    echo "ERROR: JS file mismatch! Built: $BUILT_JS, Copied: $COPIED_JS"
    echo "Checking what's in the deploy directory..."
    ls -la /var/www/beauty-specialist/frontend/dist/
    ls -la /var/www/beauty-specialist/frontend/dist/assets/
    cat /var/www/beauty-specialist/frontend/dist/index.html | grep -o 'assets/[^"]*\.js'
    exit 1
fi
echo "✓ JS file hash matches: $COPIED_JS"

# Final verification - check that the copied index.html is different from old version
if [ "$COPIED_JS" = "index-DC34i42h.js" ]; then
    echo "ERROR: Copied JS is still the OLD file! Deployment failed!"
    exit 1
fi
echo "✓ Copied JS is NEW (not old cached version)"

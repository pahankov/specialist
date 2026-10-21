#!/bin/bash
# Finalize stage of the deploy: permissions -> nginx config -> restart -> checks.
# Called from .github/workflows/deploy.yml with the repo root as $1.
# Mirrors script_stop:true -> set -e.
set -e

ROOT="${1:?usage: bash scripts/deploy_finalize.sh /var/www/beauty-specialist}"

# Fix log directory permissions (service runs as www-data)
sudo chown -R www-data:www-data "$ROOT/online-booking/backend/logs/"
sudo chmod -R 755 "$ROOT/online-booking/backend/logs/"

# Uploaded photos/certificates are written by the backend under www-data.
# The deploy starts with `chown -R deploy:deploy`, so restore write access
# here; otherwise avatar uploads fail with Permission denied.
sudo mkdir -p "$ROOT/online-booking/backend/app/static/avatars"
sudo chown -R www-data:www-data "$ROOT/online-booking/backend/app/static"
sudo chmod -R u+rwX,go+rX "$ROOT/online-booking/backend/app/static"

# Write nginx config with SSL (fixes broken configs from previous deploys)
if [ ! -f "$ROOT/scripts/deploy_fix_nginx.sh" ]; then
    echo "ERROR: scripts/deploy_fix_nginx.sh not found!"
    ls -la "$ROOT/"
    exit 1
fi
bash "$ROOT/scripts/deploy_fix_nginx.sh"

# Restart
sudo systemctl restart beauty-backend
sudo systemctl restart nginx

# Wait for backend
sleep 5

# Check backend is running and listening
echo "=== BACKEND CHECK ==="
(systemctl status beauty-backend --no-pager 2>&1 | head -10) || true
(ss -tlnp | grep 8000) || echo "Port 8000 NOT listening"

# Simple health check — just verify service is active
if systemctl is-active --quiet beauty-backend; then
    echo "=== DEPLOYMENT SUCCESSFUL ==="
else
    echo "ERROR: beauty-backend service is not active!"
    exit 1
fi

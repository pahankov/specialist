#!/bin/bash
# Write systemd service unit — uses EnvironmentFile to read .env properly
# Write to temp script, then run with sudo bash to avoid permission issues
cat > /tmp/_deploy_unit.sh << 'SCRIPT'
#!/bin/bash
# Use sudo tee instead of cat > to avoid permission denied
echo '[Unit]
Description=Beauty Specialist Backend API
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/beauty-specialist/online-booking/backend
EnvironmentFile=/var/www/beauty-specialist/online-booking/backend/.env
Environment=APP_ENV=production
ExecStart=/var/www/beauty-specialist/online-booking/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target' | sudo tee /etc/systemd/system/beauty-backend.service > /dev/null
sudo systemctl daemon-reload
# Do NOT restart here: migrations and frontend build still have to run.
# Restarting now would serve new code against the old schema. The restart
# happens in deploy_finalize.sh after alembic has finished.
SCRIPT
sudo bash /tmp/_deploy_unit.sh

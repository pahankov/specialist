#!/bin/bash
# Write systemd service unit — uses EnvironmentFile to read .env properly
# First ensure deploy has NOPASSWD for cp (idempotent)
sudo bash -c 'echo "deploy ALL=(ALL) NOPASSWD: /usr/bin/cp" > /etc/sudoers.d/99-deploy-cp && chmod 440 /etc/sudoers.d/99-deploy-cp'

# Write unit to /tmp then copy with sudo
cat > /tmp/beauty-backend.service << 'SVCEOF'
[Unit]
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
WantedBy=multi-user.target
SVCEOF
sudo cp /tmp/beauty-backend.service /etc/systemd/system/beauty-backend.service
sudo systemctl daemon-reload

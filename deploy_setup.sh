#!/bin/bash
# Write systemd service with DATABASE_URL
cat > /etc/systemd/system/beauty-backend.service << 'SVCEOF'
[Unit]
Description=Beauty Specialist Backend API
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/beauty-specialist/online-booking/backend
Environment="PATH=/var/www/beauty-specialist/online-booking/backend/venv/bin"
Environment="DATABASE_URL=postgresql+asyncpg://specialist:Postgres2024!Secure@localhost:5432/online_booking"
ExecStart=/var/www/beauty-specialist/online-booking/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF
sudo systemctl daemon-reload

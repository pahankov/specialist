# deploy.ps1 — Автоматический деплой на сервер beauty-specialist.ru

$ServerIP = "194.226.123.249"
$ServerUser = "root"
$ServerPass = "4ZjGjGzWhEtxVfVp"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Deploy to beauty-specialist.ru" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Функция для выполнения команд на сервере
function Invoke-RemoteCommand {
    param($Command)
    $escaped = $Command -replace '"', '\"' -replace '`', '\`'
    $fullCommand = "sshpass -p `"$ServerPass`" ssh -o StrictHostKeyChecking=no $ServerUser`@$ServerIP `"$escaped`""
    Invoke-Expression $fullCommand
}

# Шаг 0: Swap 2 ГБ
Write-Host "[0/12] Настройка swap 2 ГБ..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
dd if=/dev/zero of=/swapfile bs=1M count=2048
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' >> /etc/sysctl.conf
sysctl -p
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 1: Обновление системы
Write-Host "[1/12] Обновление системы..." -ForegroundColor Yellow
Invoke-RemoteCommand "apt update && apt upgrade -y"
Write-Host "  OK" -ForegroundColor Green

# Шаг 1.1: Базовые утилиты
Write-Host "[1.1/12] Установка базовых утилит..." -ForegroundColor Yellow
Invoke-RemoteCommand "apt install -y curl wget git unzip jq htop"
Write-Host "  OK" -ForegroundColor Green

# Шаг 1.2: Firewall
Write-Host "[1.2/12] Настройка firewall..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 1.3: Пользователь deploy
Write-Host "[1.3/12] Создание пользователя deploy..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
useradd -m -s /bin/bash deploy
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
echo 'deploy ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 2: Docker
Write-Host "[2/12] Установка Docker..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
apt install -y docker.io docker-compose-plugin
systemctl enable docker
systemctl start docker
usermod -aG docker deploy
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 3: PostgreSQL
Write-Host "[3/12] Установка PostgreSQL..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
apt install -y postgresql postgresql-contrib
systemctl enable postgresql
systemctl start postgresql
sudo -u postgres psql -c "CREATE DATABASE online_booking;"
sudo -u postgres psql -c "CREATE USER specialist WITH PASSWORD 'Postgres2024!Secure';"
sudo -u postgres psql -c "ALTER DATABASE online_booking OWNER TO specialist;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE online_booking TO specialist;"
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 4: Python 3.12
Write-Host "[4/12] Установка Python 3.12..." -ForegroundColor Yellow
Invoke-RemoteCommand "apt install -y python3.12 python3.12-venv python3.12-dev python3-pip"
Write-Host "  OK" -ForegroundColor Green

# Шаг 5: Node.js 20
Write-Host "[5/12] Установка Node.js 20..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 6: Клонирование проекта
Write-Host "[6/12] Клонирование проекта..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
mkdir -p /var/www
cd /var/www
git clone https://github.com/pahankov/specialist.git beauty-specialist
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 7: Backend
Write-Host "[7/12] Настройка Backend..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
cd /var/www/beauty-specialist/online-booking/backend
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 7.1: Создание .env
Write-Host "[7.1/12] Создание .env..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
cat > /var/www/beauty-specialist/online-booking/backend/.env << 'ENVEOF'
APP_NAME=Beauty Specialist API
APP_ENV=development

DATABASE_URL=postgresql+psycopg2://specialist:Postgres2024!Secure@localhost:5432/online_booking

SECRET_KEY=beauty-specialist-2024-8f3a9c7d2e1b5f4a6c8d9e0f1a2b3c4d
REFRESH_SECRET_KEY=beauty-refresh-2024-7b2c8d3e4f5a6b7c8d9e0f1a2b3c4d5e
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256

ALLOWED_ORIGINS=https://beauty-specialist.ru

REDIS_URL=redis://localhost:6379/0

SMS_PROVIDER=fake
SMS_CODE_TTL_SECONDS=300
SMS_MAX_ATTEMPTS=3

DADATA_API_KEY=07c167324787848e78b070373c5de217fff9fb52
DADATA_SECRET=78368de41f0c54a0ab401ca0367933092cdbbb80

TELEGRAM_BOT_TOKEN=8709786941:AAEaWblHPj3XCzvjrC8UL9xTXWv2DG6vxQ4
TELEGRAM_CLIENT_ID=8709786941
TELEGRAM_CLIENT_SECRET=MAEXYTXXqsyB9YUrf4ZicYr5U38WW1smzendwEBs9_FdozHY59FAaQ

VK_APP_ID=54789256
VK_SECRET_KEY=

YANDEX_CLIENT_ID=
YANDEX_CLIENT_SECRET=

MAILRU_APP_ID=
MAILRU_SECRET_KEY=

OAUTH_REDIRECT_URL=https://beauty-specialist.ru/auth/callback
ENVEOF
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 7.2: Миграции
Write-Host "[7.2/12] Применение миграций..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
cd /var/www/beauty-specialist/online-booking/backend
source venv/bin/activate
alembic upgrade head
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 7.3: Systemd сервис
Write-Host "[7.3/12] Создание systemd сервиса..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
cat > /etc/systemd/system/beauty-backend.service << 'SVCEOF'
[Unit]
Description=Beauty Specialist Backend API
After=network.target postgresql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/beauty-specialist/online-booking/backend
Environment="PATH=/var/www/beauty-specialist/online-booking/backend/venv/bin"
ExecStart=/var/www/beauty-specialist/online-booking/backend/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable beauty-backend
systemctl start beauty-backend
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 8: Frontend
Write-Host "[8/12] Сборка Frontend..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
cd /var/www/beauty-specialist/online-booking/frontend
npm ci
cat > .env.production << 'EOF'
VITE_API_URL=https://beauty-specialist.ru/api/v1
EOF
npm run build
mkdir -p /var/www/beauty-specialist/frontend/dist
cp -r dist/* /var/www/beauty-specialist/frontend/dist/
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 9: Nginx
Write-Host "[9/12] Настройка Nginx..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
apt install -y nginx
cat > /etc/nginx/sites-available/beauty-specialist << 'NGINXEOF'
# Redirect HTTP → HTTPS
server {
    listen 80;
    server_name beauty-specialist.ru www.beauty-specialist.ru;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name beauty-specialist.ru www.beauty-specialist.ru;

    # SSL
    ssl_certificate /etc/letsencrypt/live/beauty-specialist.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/beauty-specialist.ru/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # Frontend - static files
    location / {
        root /var/www/beauty-specialist/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Backend API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Swagger docs
    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_set_header Host $host;
    }
}
NGINXEOF

ln -s /etc/nginx/sites-available/beauty-specialist /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
systemctl enable nginx
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 10: SSL
Write-Host "[10/12] Установка SSL (Let's Encrypt)..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
apt install -y certbot python3-certbot-nginx
certbot --nginx -d beauty-specialist.ru -d www.beauty-specialist.ru --non-interactive --agree-tos --email your-email@example.com
"@
Write-Host "  OK" -ForegroundColor Green

# Шаг 11: Проверка
Write-Host "[11/12] Проверка сервисов..." -ForegroundColor Yellow
Invoke-RemoteCommand "systemctl status beauty-backend --no-pager"
Invoke-RemoteCommand "systemctl status nginx --no-pager"
Write-Host "  OK" -ForegroundColor Green

# Шаг 12: SSH ключ для GitHub Actions
Write-Host "[12/12] Настройка SSH для GitHub Actions..." -ForegroundColor Yellow
Invoke-RemoteCommand @"
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILc2F+wSnap84R5iUAm/m46qMx7K+XIroYfXKmHWreMk github-actions' > /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
"@
Write-Host "  OK" -ForegroundColor Green

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   DEPLOY COMPLETE!" -ForegroundColor Green
Write-Host "   Frontend: https://beauty-specialist.ru" -ForegroundColor White
Write-Host "   API: https://beauty-specialist.ru/api/v1" -ForegroundColor White
Write-Host "   Swagger: https://beauty-specialist.ru/docs" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green

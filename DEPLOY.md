# Деплой beauty-specialist.ru

## Сервер

| Параметр | Значение |
|----------|----------|
| Провайдер | Selectel VPS |
| IP | `REDACTED_SERVER_IP` |
| ОС | Ubuntu 24.04 LTS |
| vCPU | 1 ядро |
| RAM | 1 ГБ (+ 2 ГБ swap) |
| Диск | 10 ГБ |
| Домен | `beauty-specialist.ru` (через Cloudflare, DNS only / серая тучка) |
| SSH | `root` / `REDACTED_SSH_PASSWORD` |

## Архитектура

```
beauty-specialist.ru (Cloudflare DNS only)
    │
    └── Nginx (port 80→443, SSL Let's Encrypt)
        ├── /api/* → http://127.0.0.1:8000 (Backend FastAPI)
        └── /*     → /var/www/beauty-specialist/frontend/dist (Frontend static)
```

**Потребление RAM:**
- Nginx: ~3-5 МБ
- PostgreSQL: ~50-80 МБ
- Python/uvicorn: ~120-170 МБ
- Swap: 2 ГБ (защита от OOM)
- **Итого: ~200-300 МБ** (из 1 ГБ + swap)

## Установленные компоненты

### 1. Swap 2 ГБ
```bash
dd if=/dev/zero of=/swapfile bs=1M count=2048
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile
echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' >> /etc/sysctl.conf
sysctl -p
```

### 2. Базовые утилиты
```bash
apt install -y curl wget git unzip jq htop
```

### 3. Firewall (UFW)
```bash
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

### 4. Пользователь deploy
```bash
useradd -m -s /bin/bash deploy
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
echo 'deploy ALL=(ALL) NOPASSWD: ALL' > /etc/sudoers.d/deploy
chmod 440 /etc/sudoers.d/deploy
```

### 5. Docker (установлен, но не используется)
```bash
# Docker CE установлен из официального репозитория
# Не используется из-за ограничений RAM (1 ГБ)
# Проект запущен нативно
```

### 6. PostgreSQL 16
```bash
apt install -y postgresql postgresql-contrib
systemctl enable postgresql
systemctl start postgresql

# БД и пользователь
sudo -u postgres psql -c "CREATE DATABASE online_booking;"
sudo -u postgres psql -c "CREATE USER specialist WITH PASSWORD '<POSTGRES_PASSWORD>';"
sudo -u postgres psql -c "ALTER DATABASE online_booking OWNER TO specialist;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE online_booking TO specialist;"
```

**Важно:** При создании таблиц вручную через `psql` нужно также создавать ENUM-типы:
```sql
CREATE TYPE userrole AS ENUM ('MASTER', 'CLIENT', 'ADMIN');
CREATE TYPE masterstatus AS ENUM ('ACTIVE', 'INACTIVE', 'SUSPENDED');
```

### 7. Python 3.12
```bash
apt install -y python3.12 python3.12-venv python3.12-dev python3-pip
```

### 8. Node.js 20
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

### 9. Backend (FastAPI + uvicorn)
```bash
cd /var/www/beauty-specialist/online-booking/backend
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install asyncpg  # async PostgreSQL driver
```

**Файл `.env`:**
```bash
cat > /var/www/beauty-specialist/online-booking/backend/.env << 'ENVEOF'
APP_NAME=Beauty Specialist API
APP_ENV=development

DATABASE_URL=postgresql+asyncpg://specialist:<POSTGRES_PASSWORD>@localhost:5432/online_booking

SECRET_KEY=<SECRET_KEY>
REFRESH_SECRET_KEY=<REFRESH_SECRET_KEY>
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
ALGORITHM=HS256

ALLOWED_ORIGINS=https://beauty-specialist.ru

REDIS_URL=redis://localhost:6379/0

SMS_PROVIDER=fake
SMS_CODE_TTL_SECONDS=300
SMS_MAX_ATTEMPTS=3

DADATA_API_KEY=<DADATA_API_KEY>
DADATA_SECRET=<DADATA_SECRET>

TELEGRAM_BOT_TOKEN=<TELEGRAM_BOT_TOKEN>
TELEGRAM_CLIENT_ID=<TELEGRAM_CLIENT_ID>
TELEGRAM_CLIENT_SECRET=<TELEGRAM_CLIENT_SECRET>

VK_APP_ID=<VK_APP_ID>
VK_SECRET_KEY=

YANDEX_CLIENT_ID=
YANDEX_CLIENT_SECRET=

MAILRU_APP_ID=
MAILRU_SECRET_KEY=

OAUTH_REDIRECT_URL=https://beauty-specialist.ru/auth/callback
ENVEOF
```

**Файл `alembic.ini`:**
```bash
# Важно: изменить URL на PostgreSQL
sed -i 's|sqlite:///./online_booking.db|postgresql+psycopg2://specialist:<POSTGRES_PASSWORD>@localhost:5432/online_booking|' alembic.ini
```

**Создание таблиц:**
Первая миграция (`9a9c2edb119f`) пустая — не создаёт таблицы. Нужно создать вручную:
```bash
cd /var/www/beauty-specialist/online-booking/backend
python -c "
from sqlalchemy import create_engine
from app.database import Base
from app.models.user import User
from app.models.master_profile import MasterProfile
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.working_hour import WorkingHour
from app.models.audit_log import AuditLog
from app.models.blocked_slot import BlockedSlot
from app.models.country import Country
from app.models.city import City
from app.models.refresh_token import RefreshToken
from app.models.otp_code import OtpCode
engine = create_engine('postgresql+psycopg2://specialist:<POSTGRES_PASSWORD>@localhost:5432/online_booking')
Base.metadata.create_all(engine)
print('Tables created!')
"
```

**Пометить миграции как применённые:**
```bash
sudo -u postgres psql -d online_booking -c "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL); INSERT INTO alembic_version (version_num) VALUES ('08fbbef38349');"
```

**Systemd сервис:**
```bash
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
```

**Папка логов:**
```bash
mkdir -p /var/www/beauty-specialist/online-booking/backend/logs
chown -R www-data:www-data /var/www/beauty-specialist/online-booking/backend/logs
```

### 10. Frontend (React + Vite)
```bash
cd /var/www/beauty-specialist/online-booking/frontend
npm ci

# Важно: VITE_API_URL без /api/v1 — путь добавляется в коде фронтенда
cat > .env.production << 'EOF'
VITE_API_URL=https://beauty-specialist.ru
EOF

npm run build
mkdir -p /var/www/beauty-specialist/frontend/dist
cp -r dist/* /var/www/beauty-specialist/frontend/dist/
```

### 11. Nginx
```bash
apt install -y nginx

cat > /etc/nginx/sites-available/beauty-specialist << 'NGINXEOF'
server {
    listen 80;
    server_name beauty-specialist.ru www.beauty-specialist.ru;

    location / {
        root /var/www/beauty-specialist/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
        proxy_set_header Host $host;
    }

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
```

### 12. SSL (Let's Encrypt)
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d beauty-specialist.ru -d www.beauty-specialist.ru --non-interactive --agree-tos --email pahankov@mail.ru
```
Сертификат действителен до **26 декабря 2026**. Автообновление настроено.

### 13. Cloudflare
- Домен `beauty-specialist.ru` через Cloudflare
- **DNS записи A/AAAA должны быть серые** (DNS only, не оранжевая тучка)
- Иначе Cloudflare возвращает 530 (Origin is down)

### 14. GitHub Actions (CI/CD)
**Секреты репозитория:**
- `SERVER_HOST` = `REDACTED_SERVER_IP`
- `SERVER_USER` = `deploy`
- `SERVER_SSH_KEY` = содержимое приватного SSH-ключа (файл без `.pub`)

**SSH-ключ на сервере:**
```bash
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILc2F+wSnap84R5iUAm/m46qMx7K+XIroYfXKmHWreMk github-actions' > /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
chown -R deploy:deploy /home/deploy/.ssh
```

**Workflow** — файл `.github/workflows/deploy.yml`

## Полезные команды

### Проверка сервисов
```bash
systemctl status beauty-backend --no-pager
systemctl status nginx --no-pager
systemctl status postgresql --no-pager
```

### Логи
```bash
journalctl -u beauty-backend --no-pager -n 30
journalctl -u nginx --no-pager -n 30
```

### Перезапуск
```bash
systemctl restart beauty-backend
systemctl restart nginx
```

### Проверка API
```bash
curl https://beauty-specialist.ru/api/v1/masters/
curl https://beauty-specialist.ru/api/v1/services/
curl https://beauty-specialist.ru/docs  # Swagger
```

### Проверка RAM
```bash
free -h
top -bn1 | head -10
```

## Известные проблемы и решения

### 1. Таблицы не видны бэкенду
Проблема: таблицы создаются от `postgres`, а бэкенд подключается как `specialist`.
Решение: `ALTER SCHEMA public OWNER TO specialist;`

### 2. ENUM-типы не созданы
Проблема: `role` column type mismatch.
Решение:
```sql
CREATE TYPE userrole AS ENUM ('MASTER', 'CLIENT', 'ADMIN');
CREATE TYPE masterstatus AS ENUM ('ACTIVE', 'INACTIVE', 'SUSPENDED');
ALTER TABLE users ALTER COLUMN role DROP DEFAULT;
ALTER TABLE users ALTER COLUMN role TYPE userrole USING CASE role WHEN 'MASTER' THEN 'MASTER'::userrole WHEN 'ADMIN' THEN 'ADMIN'::userrole ELSE 'CLIENT'::userrole END;
ALTER TABLE users ALTER COLUMN role SET DEFAULT 'CLIENT';
```

### 3. Дублирование `/api/v1/api/v1/`
Проблема: `VITE_API_URL` содержит `/api/v1`, а код фронтенда добавляет его снова.
Решение: `VITE_API_URL=https://beauty-specialist.ru` (без `/api/v1`)

### 4. Cloudflare 530
Проблема: Cloudflare проксирует трафик, но origin не доступен.
Решение: Отключить прокси в Cloudflare (серая тучка в DNS записях)

### 5. PostgreSQL password с `!`
Проблема: bash интерпретирует `!` в двойных кавычках.
Решение: использовать одинарные кавычки или `set +H`

## Структура на сервере
```
/var/www/beauty-specialist/
├── online-booking/
│   ├── backend/
│   │   ├── .env
│   │   ├── alembic.ini
│   │   ├── alembic/
│   │   ├── app/
│   │   ├── logs/
│   │   ├── requirements.txt
│   │   └── venv/
│   └── frontend/
│       ├── .env.production
│       ├── dist/           # собранный фронтенд
│       └── src/
└── frontend/
    └── dist/               # копия для Nginx
```

## Системные пользователи
- `root` — полный доступ
- `deploy` — для GitHub Actions (sudo без пароля)
- `www-data` — владелец процесса бэкенда
- `postgres` — PostgreSQL

## Порты
- `80` — HTTP (Nginx)
- `443` — HTTPS (Nginx + SSL)
- `8000` — Backend (localhost, только Nginx прокси)
- `5432` — PostgreSQL (localhost)

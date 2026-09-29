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
Больше не нужно менять вручную — URL берётся из переменной окружения `DATABASE_URL` через `alembic/env.py`.

**Создание таблиц:**
Больше не нужно создавать вручную — baseline-миграция `4fdb5e791ead` создаёт все 14 таблиц автоматически при `alembic upgrade head`.

**Пометить миграции как применённые:**
Больше не нужно — `alembic upgrade head` сам применяет все миграции.

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
- `SERVER_SSH_KEY` = содержимое приватного SSH-ключа (файл без `.pub`)
- `DATABASE_URL` = `postgresql+asyncpg://specialist:<POSTGRES_PASSWORD>@localhost:5432/online_booking`

**Workflow** — файл `.github/workflows/deploy.yml`

## Миграции БД

### Как работают миграции

Миграции Alembic — это скрипты, которые изменяют структуру БД. При каждом push в `main` GitHub Actions автоматически применяет все миграции на сервере через `alembic upgrade head`.

**Полная цепочка миграций (линейная, без ветвлений):**
→ `9a9c2edb119f` (initial_schema — пустая) → `08fbbef38349` (master_status enum + working_hour.is_active) → `f43f84fe3057` (timezone fix: все DateTime → TIMESTAMP WITH TIME ZONE) → `sync_missing_columns` (no_show_count, preferred_service_ids, name_ru/name_en в countries) → `aaa7fcc30d47` (name_ru в countries) → `b2e8f1a3c9d0` (name_en в cities) → `4fdb5e791ead` (baseline: создаёт все 14 таблиц)

### Как сгенерировать новую миграцию

```bash
cd online-booking/backend
# Локально (SQLite)
$env:DATABASE_URL = "sqlite+aiosqlite:///./dev.db"
python -m alembic revision --autogenerate -m "описание изменений"
python -m alembic upgrade head
```

Alembic читает `DATABASE_URL` из переменной окружения через `alembic/env.py`. Если переменная не set — используется SQLite по умолчанию из `alembic.ini`.

### Проверка миграций

```bash
python -m alembic history        # показать цепочку
python -m alembic current        # текущая версия в БД
python -m alembic upgrade head   # применить все
python -m alembic downgrade -1   # откат на одну версию
```

### Как работает деплой

1. Push в main → запускается `.github/workflows/deploy.yml`
2. Подключение к серверу по SSH (секреты `SERVER_HOST`, `SERVER_SSH_KEY`)
3. `git pull origin main`
4. `export DATABASE_URL="${DATABASE_URL}"` — передаёт URL БД из GitHub Secrets
5. `alembic upgrade head` — применяет все 7 миграций
6. `create_superuser_sync.py` — создаёт/обновляет админа (pahankov@mail.ru)
7. `seed_production.py` — заполняет БД тестовыми данными если пуста
8. Сборка фронтенда (`npm ci` + `npm run build`)
9. Копирование статики в `/var/www/beauty-specialist/frontend/dist/`
10. Перезапуск beauty-backend + nginx

### GitHub Secrets

Обязательно настроить в Settings → Secrets and variables → Actions → New repository secret:

| Secret | Описание | Пример |
|--------|----------|--------|
| `SERVER_HOST` | IP сервера | `REDACTED_SERVER_IP` |
| `SERVER_SSH_KEY` | Приватный SSH-ключ | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DATABASE_URL` | URL PostgreSQL для миграций | `postgresql+asyncpg://specialist:<POSTGRES_PASSWORD>@localhost:5432/online_booking` |

> **Без `DATABASE_URL` миграции не подключатся к БД!**

### Структура миграций

Файлы находятся в `online-booking/backend/alembic/versions/`:

| Файл | Что делает |
|------|------------|
| `9a9c2edb119f_initial_schema.py` | Пустая — таблицы создаются через baseline |
| `08fbbef38349_add_master_status_enum...py` | Enum `MasterStatus` + `WorkingHour.is_active` |
| `f43f84fe3057_fix_timezone_in_datetime...py` | Все `DateTime` → `TIMESTAMP WITH TIME ZONE`, удаление старых таблиц |
| `sync_missing_columns.py` | Добавляет `no_show_count`, `preferred_service_ids`, `name_ru`/`name_en` в countries |
| `aaa7fcc30d47_add_name_ru_to_countries.py` | `name_ru` в countries (idempotent) |
| `b2e8f1a3c9d0_add_cities_name_en.py` | `name_en` в cities |
| `4fdb5e791ead_baseline_capture_current_schema.py` | Baseline — создаёт все 14 таблиц, 31+ колонок, индексы |

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

## Чеклист при добавлении нового функционала

При добавлении **любой новой модели, эндпоинта или изменения БД** — проверяйте все пункты:

### 1. Модель и схема
- [ ] Модель создана в `app/models/`
- [ ] Pydantic-схемы (create/update/response) в `app/schemas/`
- [ ] Enum-типы для статусов/ролей определены

### 2. Миграция БД
- [ ] Миграция сгенерирована: `python -m alembic revision --autogenerate -m "описание"`
- [ ] Миграция протестирована локально: `python -m alembic upgrade head`
- [ ] Миграция добавлена в цепочку в `DEPLOY.md` (раздел "Полная цепочка миграций")
- [ ] Миграция idempotent (не падает при повторном запуске)

### 3. Данные (самая частая ошибка!)
- [ ] **Сид-данные** для новой таблицы созданы (если таблица должна содержать записи)
- [ ] Сид-данные добавлены в `seed_test_data.py` ИЛИ в отдельный скрипт
- [ ] Сид-данные вызываются из `seed_production.py`
- [ ] **Связанные таблицы** заполнены (foreign key записи)
- [ ] На чистом сервере данные появляются автоматически при деплое

### 4. API и роутер
- [ ] Эндпоинты добавлены в router
- [ ] Router подключён в `app/main.py`
- [ ] API-клиент на фронтенде обновлён (`api/client.ts`)
- [ ] Swagger документация доступна (`/api/v1/docs`)

### 5. Фронтенд
- [ ] Компоненты обновлены/добавлены
- [ ] Стили добавлены (если нужно)
- [ ] Обработка ошибок и loading states
- [ ] Пустые состояния (empty states) — что показывать если данных нет
- [ ] На чистом сервере компонент работает с сид-данными

### 6. Авторизация и роли
- [ ] Эндпоинты защищены (`Depends(require_admin)` и т.д.)
- [ ] Роутинг на фронтенде учитывает роли (`getIsAdmin()`)
- [ ] Суперпользователь создаётся в `create_superuser_sync.py`
- [ ] Суперпользователь имеет **все связанные записи** (MasterProfile, etc.)

### 7. Деплой
- [ ] `deploy.yml` запускает все необходимые скрипты в правильном порядке:
  1. `alembic upgrade head` — миграции
  2. `create_superuser_sync.py` — суперпользователь
  3. `fix_production_db.py` — исправления БД
  4. `seed_production.py` — сид-данные
  5. `create_minimal_reviews.py` — данные для карусели
- [ ] Frontend собирается с правильными `.env` переменными
- [ ] Сервисы перезапускаются после деплоя

### 8. Тесты
- [ ] Backend-тесты обновлены (`tests/`)
- [ ] Фронтенд-тесты обновлены (`src/tests/`)
- [ ] CI pipeline проходит (`ci.yml`)

### 9. Документация
- [ ] `DEPLOY.md` обновлён (цепочка миграций, новые скрипты)
- [ ] Изменения в API задокументированы в Swagger
- [ ] Changelog обновлён (`/api/v1/admin/changelog`)

### 10. Финальная проверка на чистом сервере
- [ ] `GET /api/v1/health` — 200 OK
- [ ] `GET /api/v1/countries/` — 200 OK с данными
- [ ] `POST /api/v1/auth/login-unified` — вход суперпользователя работает
- [ ] Админ-панель открывается
- [ ] Карусель на главной показывает все 3 слайда
- [ ] Отзывы отображаются в карусели
- [ ] Регистрация/авторизация мастеров работает

---

**Частые ошибки при забывании пунктов:**

| Забыли | Результат | Как обнаружить |
|--------|-----------|----------------|
| Сид-данные для новой таблицы | 500 ошибка на API | `curl https://beauty-specialist.ru/api/v1/new-endpoint/` |
| Связанную запись (MasterProfile) | 500 ошибка при логине | `journalctl -u beauty-backend -n 50` |
| Сид-данные для отзывов | Пустая карусель | Открыть главную страницу |
| Обновить `deploy.yml` | На сервере старые данные | Проверить логи деплоя |
| Empty state компонента | Белый экран | Открыть страницу на чистом сервере |

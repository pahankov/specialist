# Деплой beauty-specialist.ru

> **ПОСЛЕДНЕЕ ОБНОВЛЕНИЕ:** 30 сентября 2026
> **СТАТУС:** ✅ Сайт работает, деплой автоматизирован
> **ГЛАВНОЕ ПРАВИЛО:** НЕ использовать `SAEnum` в моделях SQLAlchemy (см. раздел 1)

## Сервер

| Параметр | Значение |
|----------|----------|
| Провайдер | Selectel VPS |
| IP | `194.226.123.249` |
| ОС | Ubuntu 24.04 LTS |
| vCPU | 1 ядро |
| RAM | 1 ГБ (+ 2 ГБ swap) |
| Диск | 10 ГБ |
| Домен | `beauty-specialist.ru` (через Cloudflare, DNS only / серая тучка) |
| SSH | `root` / `4ZjGjGzWhEtxVfVp` |

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
```

> ⚠️ **НЕ создавайте `masterstatus` enum!** В моделях используется `String(20)` вместо `SAEnum`.

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

**Systemd сервис (КРИТИЧНО!):**
```bash
cat > /etc/systemd/system/beauty-backend.service << 'SVCEOF'
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

systemctl daemon-reload
systemctl enable beauty-backend
systemctl start beauty-backend
```
**ВАЖНО:**
- `EnvironmentFile=.env` — читает `DATABASE_URL` из `.env` (НЕ `Environment="DATABASE_URL=..."!`)
- `Environment=APP_ENV=production` — форсирует PostgreSQL вместо SQLite
- Без этих двух строк бэкенд падает на SQLite → 502 Bad Gateway

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
- `SERVER_HOST` = `194.226.123.249`
- `SERVER_SSH_KEY` = содержимое приватного SSH-ключа (файл без `.pub`)
- `DATABASE_URL` = `postgresql+asyncpg://specialist:<POSTGRES_PASSWORD>@localhost:5432/online_booking`

**Workflow** — файл `.github/workflows/deploy.yml`

## Миграции БД

### Как работают миграции

Миграции Alembic — это скрипты, которые изменяют структуру БД. При каждом push в `main` GitHub Actions автоматически применяет все миграции на сервере через `alembic upgrade head`.

**Полная цепочка миграций (линейная, без ветвлений):**
→ `9a9c2edb119f` (initial_schema — пустая) → `08fbbef38349` (master_status string + working_hour.is_active) → `f43f84fe3057` (timezone fix) → `sync_missing_columns` (no_show_count, preferred_service_ids) → `aaa7fcc30d47` (name_ru в countries) → `b2e8f1a3c9d0` (name_en в cities) → `4fdb5e791ead` (baseline: IF NOT EXISTS) → `5c72771` (audit_logs FK → users вместо master_profiles, чтобы админ мог логировать действия)

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
5. **`fix_all_tables.sql`** — исправляет схему БД (добавляет недостающие колонки, конвертирует enum в VARCHAR)
6. `alembic upgrade head` — применяет все миграции
7. `create_superuser.py` — создаёт/обновляет админа (pahankov@mail.ru)
8. `fix_production_db.py` — дополнительные исправления БД
9. `seed_production.py` — заполняет БД тестовыми данными если пуста
10. `create_minimal_reviews.py` — создаёт отзывы для карусели
11. Сборка фронтенда (`npm ci` + `npm run build`)
12. Копирование статики в `/var/www/beauty-specialist/frontend/dist/`
13. Перезапуск beauty-backend + nginx
14. **Тесты API** — проверка health, countries, login, reviews

### GitHub Secrets

Обязательно настроить в Settings → Secrets and variables → Actions → New repository secret:

| Secret | Описание | Пример |
|--------|----------|--------|
| `SERVER_HOST` | IP сервера | `194.226.123.249` |
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

### 2. Дублирование `/api/v1/api/v1/`
Проблема: `VITE_API_URL` содержит `/api/v1`, а код фронтенда добавляет его снова.
Решение: `VITE_API_URL=https://beauty-specialist.ru` (без `/api/v1`)

### 3. Cloudflare 530
Проблема: Cloudflare проксирует трафик, но origin не доступен.
Решение: Отключить прокси в Cloudflare (серая тучка в DNS записях)

### 4. PostgreSQL password с `!`
Проблема: bash интерпретирует `!` в двойных кавычках.
Решение: использовать одинарные кавычки или `set +H`

### 5. 502 Bad Gateway — бэкенд не запускается
Проблема: сервис `beauty-backend` неактивен, nginx возвращает 502.
Причина: сервис запускается от `www-data`, но директория `logs/` принадлежит `deploy`.
Решение:
```bash
sudo chown -R www-data:www-data /var/www/beauty-specialist/online-booking/backend/logs/
sudo chmod -R 755 /var/www/beauty-specialist/online-booking/backend/logs/
sudo systemctl restart beauty-backend
```
Проверка: `sudo systemctl status beauty-backend --no-pager`

### 6. 500 Internal Server Error — column X does not exist
Проблема: модель ожидает колонку, которой нет в production БД.
Причина: схема БД не соответствует модели SQLAlchemy.
Решение: запустить `fix_all_tables.sql`:
```bash
cd /var/www/beauty-specialist/online-booking/backend
sudo -u postgres psql -d online_booking -f fix_all_tables.sql
```

### 7. 500 Internal Server Error — LookupError enum
Проблема: `LookupError: 'active' is not among the defined enum values`
Причина: в модели используется `SAEnum`, asyncpg кэширует старый enum-тип.
Решение: заменить `SAEnum` на `String(20)` в модели и `.value` на прямое значение в коде.

---

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

## Быстрый деплой

### Автоматический скрипт `deploy.sh`

```bash
# Продакшен (требует DATABASE_URL)
export DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/dbname'
./deploy.sh

# Локально (SQLite)
./deploy.sh --local

# Только проверка без изменений
./deploy.sh --dry-run
```

Скрипт автоматически:
1. Проверяет и исправляет схему БД (добавляет недостающие колонки)
2. Запускает миграции Alembic
3. Создаёт/обновляет суперпользователя
4. Заполняет seed-данными
5. Собирает фронтенд
6. Перезапускает сервисы
7. Проверяет что всё работает

---

## Чеклист при добавлении нового функционала

При добавлении **любой новой модели, эндпоинта или изменения БД** — проверяйте все пункты:

### 1. Модель и схема
- [ ] Модель создана в `app/models/`
- [ ] Pydantic-схемы (create/update/response) в `app/schemas/`
- [ ] **НЕТ `SAEnum` или `Enum()` в моделях** — использовать `String(20)` вместо enum
- [ ] В коде НЕ использовать `.value` у status (например, `mp.status` а не `mp.status.value`)

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
- [ ] `GET /api/v1/masters/` — 200 OK с данными
- [ ] `GET /api/v1/reviews/` — 200 OK с отзывами
- [ ] `POST /api/v1/auth/login-unified` — вход суперпользователя работает
- [ ] Админ-панель открывается
- [ ] Карусель на главной показывает отзывы
- [ ] Регистрация/авторизация мастеров работает

---

## КРИТИЧЕСКИЕ ОШИБКИ И ИХ ПРИЧИНЫ

### 1. 502 Bad Gateway — бэкенд на SQLite
**Причина:** systemd юнит не читает `.env` (нет `EnvironmentFile=`) или `APP_ENV=development`.
**Проверка:** `cat /etc/systemd/system/beauty-backend.service` — должен содержать `EnvironmentFile=` и `APP_ENV=production`.
**Решение:** Обновить юнит (см. раздел выше) + `sudo systemctl restart beauty-backend`.

### 2. 502 — юнит не обновился после деплоя
**Причина:** `deploy_setup.sh` не имеет `sudo` для записи в `/etc/systemd/system/`.
**Решение:** `deploy_setup.sh` пишет в `/tmp`, потом `sudo bash -c 'cat > /etc/systemd/system/...' << 'UNIT'`.

### 3. Alembic: `ValueError: invalid interpolation syntax in '***'`
**Причина:** `config.set_main_option()` ломается на `!` в пароле.
**Решение:** В `alembic/env.py` НЕ использовать `config.set_main_option()`, передавать URL напрямую в `engine_from_config()`.

### 4. Alembic: `MissingGreenlet`
**Причина:** `config.get_main_option()` возвращает SQLite URL из `alembic.ini` (не пустая строка → fallback не срабатывает).
**Решение:** В `env.py` всегда проверять `DATABASE_URL` из env ПЕРВЫМ.

### 5. 500 — `ForeignKeyViolationError` (FK ссылается на users вместо master_profiles)
**Причина:** старая БД имеет FK `appointments.master_id → users`, модель ожидает `→ master_profiles`.
**Решение:** `fix_all_tables.sql` содержит блок "Fix FK constraints" — DROP и CREATE FK заново.

### 6. 500 — `ForeignKeyViolationError: audit_logs.master_id → master_profiles`
**Причина:** `audit_logs.master_id` ссылается на `master_profiles`, но админ не мастер. `log_action()` вставляет `master_id=1` (id админа).
**Решение:** `audit_logs.master_id` должен ссылаться на `users(id)`. Фикс в `fix_all_tables.sql` (строки 110-117).

### 7. seed_test_data.py падает на `MasterStatus`
**Решение:** Использовать `status="active"` вместо `status=MasterStatus.ACTIVE`.

---

## ПРАВИЛА БЕЗОПАСНОСТИ И КАЧЕСТВА КОДА

### 1. Никогда не коммить чувствительные данные
- **Никогда** не добавляй реальные пароли, API-ключи, токены в код или документацию
- В DEPLOY.md используй placeholders: `<POSTGRES_PASSWORD>`, `<SECRET_KEY>`, `<TELEGRAM_BOT_TOKEN>`
- Реальные секреты хранятся в:
  - `.env` на сервере (не в git!)
  - GitHub Secrets (`DATABASE_URL`, `SERVER_SSH_KEY`)
  - `.env.production` на сервере (не в git!)
- **Проверка:** перед коммитом выполни `git diff --cached` и убедись что нет `password`, `secret`, `token`, `key` со значениями

### 2. После любого редактирования файла — проверяй синтаксис
- Python: `python -c "import ast; ast.parse(open('file.py').read())"` или `python -c "import module_name"`
- TypeScript: `npm run type-check`
- **Никогда** не доверяй редактированию без валидации
- Если файл редактируется через скрипт — проверяй что нет null bytes (`\x00`)
- **Пример ошибки:** `audit.py` обрезался на строке 85 → `SyntaxError: '[' was never closed`

### 3. При изменении моделей SQLAlchemy — проверяй все relationship
- Если меняешь FK в модели — проверь все `back_populates` в других моделях
- Если удаляешь relationship — проверь что нигде не используется
- **Проверка:** `python -c "from app.main import app"` — если импорт падает с NoForeignKeysError — проблема в relationship
- **Пример ошибки:** `AuditLog.master_profile` удалён, но `admin/audit.py` всё ещё использовал `selectinload(AuditLog.master_profile)`

### 4. При изменении log_action — проверяй все вызовы
- log_action принимает `master_id` — убедись что это User.id (не MasterProfile.id)
- Супер-админ (role=ADMIN) не имеет MasterProfile → `master.master_profile.id` = None → AttributeError
- **Проверка:** `grep -r "log_action" app/modules/admin/` — все вызовы должны использовать `master.id`

### 5. Деплой при пуше — изменения должны быть минимальными и проверенными
- Перед коммитом: локальная проверка импорта `python -c "from app.main import app"`
- Изменения должны быть обратимыми (git commit с понятным сообщением)
- После коммита: подождать деплой, проверить логи `sudo journalctl -u beauty-backend -n 100`
- **Логи с сервера:** `ssh root@194.226.123.249` → `sudo journalctl -u beauty-backend --no-pager -n 100`

### 6. Модульная структура
- Файлы > 300 строк — делить на модули
- Один файл — одна ответственность (SRP)
- Роутеры агрегируются в `__init__.py` модуля
- Не меняй API пути — только внутреннюю структуру
- **При разделении файла — копируй ВСЕ импорты!**
- **Пример ошибки:** `crud.py` — забыл `Query` из `fastapi` → `NameError: name 'Query' is not defined`

### 7. При создании новых модулей — проверяй все зависимости
- Каждый новый файл должен пройти `python -c "import ast; ast.parse(open('file.py').read())"`
- Проверь что все импорты существуют: `from app.modules.auth.service import hash_password` (не `app.services.auth`)
- **Пример ошибки:** `hash_password` в `app.modules.auth.service`, а не в `app.services.auth`

---

## ЧЕК-ЛИСТ ПЕРЕД КОММИТОМ

> **Всегда выполняй перед `git commit`!** Это сэкономит часы на отладку.

### 1. Проверь синтаксис всех изменённых файлов
```bash
python -c "import ast; ast.parse(open('file.py').read())"
```
- **Не доверяй** редактированию без валидации
- Если файл редактировался через скрипт — проверь на null bytes

### 2. Проверь импорт всего приложения
```bash
python -c "from app.main import app"
```
- Ловит 90% ошибок до деплоя
- Если падает с `NoForeignKeysError` → проблема в relationship
- Если падает с `NameError` → проблема в импорте

### 3. Проверь ВСЕ использования при изменении модели
```bash
grep -r "old_relationship_name" app/
grep -r "log_action" app/modules/admin/
```
- Не только в новом модуле, а во всём проекте
- При смене FK — проверь все `back_populates`
- При удалении relationship — проверь что нигде не используется

### 4. Проверь все импорты в новых файлах
```bash
grep -r "def hash_password" app/  # найти точный путь
grep -r "Query" app/modules/admin/masters/  # проверить все параметры
```
- Не гадать, а искать
- При разделении файла — проверить КАЖДЫЙ endpoint, КАЖДЫЙ параметр

### 5. Проверь что не удалил используемые классы
```bash
grep -r "LoginRequest" app/modules/auth/
```
- Если удалил класс — проверь что нигде не используется

### 6. Проверь async/sync функции
- `def` — синхронная, вызывается как `result = func()`
- `async def` — асинхронная, вызывается как `result = await func()`
- **Не делай** `async def` для простых конвертеров (они не await'ятся в list comprehension)

### 7. Проверь чувствительные данные
```bash
git diff --cached | grep -i "password\|secret\|token\|key"
```
- Никаких реальных паролей в коде или документации
- В DEPLOY.md — только placeholders

---

## ТАБЛИЦА ИНЦИДЕНТОВ

> Все ошибки, которые произошли при рефакторинге. Используй для предотвращения повторений.

| Инцидент | Причина | Как обнаружил | Как исправил |
|----------|---------|---------------|---------------|
| `NoForeignKeysError` | FK в AuditLog изменён на users.id, но MasterProfile.audit_logs всё ещё ссылается на master_profile.id | `journalctl` → NoForeignKeysError | Удалить `audit_logs` из MasterProfile |
| `AttributeError: 'NoneType' object has no attribute 'id'` | `master.master_profile.id` для супер-админа (нет MasterProfile) | 502 Bad Gateway | Использовать `master.id` (User.id) |
| `audit.py` обрезался на строке 85 | Null bytes при редактировании через Python-скрипт | `SyntaxError: '[' was never closed` | Пересоздать файл полностью |
| `NameError: name 'Query' is not defined` | Забыл `Query` при разделении `masters.py` на модули | `journalctl` → NameError | Добавить `Query` в импорты |
| `NameError: name 'LoginRequest' is not defined` | Удалил класс, но он использовался в эндпоинтах | `journalctl` → NameError | Заменить на `UserLoginByEmail` из schemas |
| `ResponseValidationError: coroutine object` | `_to_response` объявлен как `async def`, но не await'ится | 500 Internal Server Error | Убрать `async` |
| `No module named 'redis'` | Redis не установлен на сервере | `journalctl` → warning | Игнорировать (fallback на отсутствие кэша) |
| `hash_password` не найден | Путь `app.services.auth` не существует | `journalctl` → ImportError | Использовать `app.modules.auth.service` |

---

## ЧАСТЫЕ ОШИБКИ ПРИ ЗАБЫВАНИИ ПУНКТОВ

| Забыли | Результат | Как обнаружить | Как исправить |
|--------|-----------|----------------|---------------|
| SAEnum в модели | 500 ошибка на ВСЕХ endpoint'ах | `journalctl -u beauty-backend -n 50` | Заменить на `String(20)` |
| `.value` у status | 500 AttributeError | `journalctl -u beauty-backend -n 50` | Убрать `.value` |
| Сид-данные для новой таблицы | 500 ошибка на API | `curl https://beauty-specialist.ru/api/v1/new-endpoint/` | Запустить `seed_production.py` |
| Связанную запись (MasterProfile) | 500 ошибка при логине | `journalctl -u beauty-backend -n 50` | Создать запись через SQL |
| Сид-данные для отзывов | Пустая карусель | Открыть главную страницу | Запустить `create_minimal_reviews.py` |
| Обновить `deploy.yml` | На сервере старые данные | Проверить логи деплоя | Добавить шаги в workflow |
| Empty state компонента | Белый экран | Открыть страницу на чистом сервере | Добавить empty state |
| Фикс схемы БД | 500 ошибка (column X does not exist) | `journalctl -u beauty-backend -n 50` | Запустить `fix_all_tables.sql` |
| Права на логи | 502 Bad Gateway | `systemctl status beauty-backend` | `chown -R www-data:www-data logs/` |

---

## ИТОГОВЫЕ ПРАВИЛА РАБОТЫ С КОДОМ

> **Эти правила были выведены в процессе рефакторинга и должны соблюдаться всегда.**

### 1. Перед коммитом — ОБЯЗАТЕЛЬНАЯ проверка (5 команд)
```bash
# 1. Синтаксис всех изменённых файлов
python -c "import ast; ast.parse(open('file.py').read())"

# 2. Импорт всего приложения (ловит 90% ошибок)
python -c "from app.main import app"

# 3. Проверка использований при изменении модели
grep -r "old_name" app/

# 4. Проверка импортов
grep -r "def function_name" app/

# 5. Проверка чувствительных данных
git diff --cached | grep -i "password\|secret\|token\|key"
```

### 2. При разделении файлов — ВСЕГДА проверять каждый endpoint
- Копировать ВСЕ импорты (не только основные)
- Проверить каждый параметр в каждом эндпоинте
- Проверить что все async/sync функции правильные

### 3. При изменении моделей SQLAlchemy — проверять ВСЕ relationship
- `FK` → все `back_populates` в других моделях
- Удаление relationship → `grep -r` по всему проекту
- `NoForeignKeysError` = рассинхрон relationship

### 4. Никогда не доверять редактированию без валидации
- После редактирования — `ast.parse()` или `python -c "import module"`
- Если файл редактировался через скрипт — проверить на null bytes

### 5. При изменении log_action — проверять ВСЕ вызовы
- `master.id` (User.id), НЕ `master.master_profile.id`
- Супер-админ не имеет MasterProfile → None.id → AttributeError

### 6. При удалении классов — проверять что нигде не используются
- `grep -r "ClassName" app/` перед удалением
- Если удалил класс из router.py — проверить эндпоинты

### 7. При создании новых модулей — проверять пути импортов
- `hash_password` в `app.modules.auth.service`, НЕ `app.services.auth`
- Искать точный путь через `grep`, НЕ гадать

### 8. Деплой при пуше — изменения должны быть минимальными
- Один коммит = одно изменение
- Понятное сообщение коммита
- После коммита — проверить логи деплоя и `journalctl`

---

## ИТОГИ ИСПРАВЛЁННЫХ ОШИБОК (REFRAIN FROM)

> Все ошибки, возникшие при рефакторинге. **Никогда не делать так:**

### 1. Никогда не использовать `master.master_profile.id` для супер-админа
**Ошибка:** `AttributeError: 'NoneType' object has no attribute 'id'` на `/masters`, `/services`, `/appointments`
**Причина:** Супер-админ (role=ADMIN) не имеет MasterProfile → `master.master_profile` = `None`
**Правило:** Всегда проверять `if master.role == UserRole.ADMIN` перед доступом к `master.master_profile`
**Проверка:** `grep -r "master.master_profile.id" app/modules/admin/` — все места должны иметь проверку роли

### 2. Никогда не удалять relationship без проверки всех использований
**Ошибка:** `NoForeignKeysError` при импорте приложения
**Причина:** Изменил FK в `AuditLog` на `users.id`, но `MasterProfile.audit_logs` всё ещё ссылался на `master_profile`
**Правило:** При изменении модели — `grep -r "old_relationship_name" app/` по ВСЕМ файлам
**Проверка:** `python -c "from app.main import app"` — падает с NoForeignKeysError = проблема в relationship

### 3. Никогда не использовать `async def` для конвертеров внутри list comprehension
**Ошибка:** `ResponseValidationError: coroutine object` на `/masters`
**Причина:** `_to_response` объявлен как `async def`, но вызывается в `[... for u in users]` без `await`
**Правило:** Конвертеры данных (`_to_response`, `_to_dict`) — всегда `def`, НЕ `async def`
**Проверка:** `grep -r "async def.*_to_" app/` — не должно быть

### 4. Никогда не удалять классы из router.py без проверки эндпоинтов
**Ошибка:** `NameError: name 'LoginRequest' is not defined`
**Причина:** Удалил `LoginRequest` и `ClientLoginRequest` из `router.py`, но они использовались в эндпоинтах
**Правило:** Перед удалением класса — `grep -r "ClassName" app/` по всему проекту
**Проверка:** `python -c "import ast; ast.parse(open('file.py').read())"`

### 5. Никогда не забывать импорты при разделении файлов
**Ошибка:** `NameError: name 'Query' is not defined`
**Причина:** Разделил `masters.py` на 6 модулей, но забыл `Query` в `crud.py`
**Правило:** При разделении файла — копировать ВСЕ импорты, проверять КАЖДЫЙ endpoint
**Проверка:** `python -c "from app.main import app"`

### 6. Никогда не использовать неверный путь импорта
**Ошибка:** `ImportError: No module named 'app.services.auth'`
**Причина:** `hash_password` в `app.modules.auth.service`, а не `app.services.auth`
**Правило:** Искать точный путь через `grep -r "def function_name" app/`, НЕ гадать
**Проверка:** `python -c "from app.modules.auth.service import hash_password"`

### 7. Никогда не доверять редактированию без валидации синтаксиса
**Ошибка:** `SyntaxError: '[' was never closed` в `audit.py`
**Причина:** Null bytes при редактировании через Python-скрипт обрезали строку
**Правило:** После любого редактирования — `python -c "import ast; ast.parse(open('file.py').read())"`
**Проверка:** Если файл редактировался через скрипт — проверить на null bytes

### 8. Никогда не использовать `settings.get()` у Pydantic BaseSettings
**Ошибка:** `AttributeError: 'BaseSettings' object has no attribute 'get'`
**Причина:** `settings` — Pydantic модель, у неё нет метода `.get()`
**Правило:** Использовать `settings.REDIS_URL` напрямую, НЕ `settings.get("REDIS_URL", ...)`
**Проверка:** `grep -r "settings.get(" app/` — не должно быть

### 9. Никогда не использовать `MasterStatus.ACTIVE` в коде (кроме service)
**Ошибка:** Инконсистентность — некоторые места используют `MasterStatus.ACTIVE`, другие `"active"`
**Причина:** Колонка `String(20)`, enum `MasterStatus` только в `master_status.py`
**Правило:** Использовать строки `"active"`, `"inactive"`, `"suspended"` везде, кроме `services/master_status.py`
**Проверка:** `grep -r "MasterStatus\." app/` — должен быть только в `master_status.py`

### 10. Никогда не использовать `role="CLIENT"` вместо enum
**Ошибка:** Инконсистентность — некоторые места используют `"CLIENT"`, другие `UserRole.CLIENT`
**Правило:** Всегда `UserRole.CLIENT`, `UserRole.ADMIN`, `UserRole.MASTER`
**Проверка:** `grep -r 'role=".*"' app/modules/admin/` — не должно быть


| Забыли | Результат | Как обнаружить | Как исправить |
|--------|-----------|----------------|---------------|
| SAEnum в модели | 500 ошибка на ВСЕХ endpoint'ах | `journalctl -u beauty-backend -n 50` | Заменить на `String(20)` |
| `.value` у status | 500 AttributeError | `journalctl -u beauty-backend -n 50` | Убрать `.value` |
| Сид-данные для новой таблицы | 500 ошибка на API | `curl https://beauty-specialist.ru/api/v1/new-endpoint/` | Запустить `seed_production.py` |
| Связанную запись (MasterProfile) | 500 ошибка при логине | `journalctl -u beauty-backend -n 50` | Создать запись через SQL |
| Сид-данные для отзывов | Пустая карусель | Открыть главную страницу | Запустить `create_minimal_reviews.py` |
| Обновить `deploy.yml` | На сервере старые данные | Проверить логи деплоя | Добавить шаги в workflow |
| Empty state компонента | Белый экран | Открыть страницу на чистом сервере | Добавить empty state |
| Фикс схемы БД | 500 ошибка (column X does not exist) | `journalctl -u beauty-backend -n 50` | Запустить `fix_all_tables.sql` |
| Права на логи | 502 Bad Gateway | `systemctl status beauty-backend` | `chown -R www-data:www-data logs/` |

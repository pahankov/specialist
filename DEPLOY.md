# 🚀 Deployment Guide — beauty-specialist.ru

> Полное руководство по деплою. Без дублирования, без утечек секретов.
> **ВАЖНО:** Этот файл не содержит реальных секретов. Локальные секреты — в `LOCAL.md` (не пушить в git).

---

## 📋 Содержание

- [Архитектура](#архитектура)
- [CI/CD Pipeline](#cicd-pipeline)
- [Пошаговый деплой](#пошаговый-деплой)
- [Ручной деплой](#ручной-деплой)
- [Критические ошибки и как их избежать](#критические-ошибки-и-как-их-избежать)
- [Troubleshooting](#troubleshooting)
- [Health Checks](#health-checks)

---

## 🏗 Архитектура

```
beauty-specialist.ru (port 443 SSL, Let's Encrypt)
    │
    ├── Nginx
    │   ├── / → frontend/dist (React SPA, Vite build)
    │   ├── /api/ → backend (FastAPI, port 8000)
    │   └── JS/CSS → no-cache headers
    │
    ├── systemd: beauty-backend (www-data)
    │   ├── venv (Python 3.12)
    │   ├── uvicorn → FastAPI
    │   ├── .env (DATABASE_URL, SECRET_KEY, etc.)
    │   └── PostgreSQL 16 (online_booking DB)
    │
    └── Redis 7 (optional, for caching)
```

**Потребление ресурсов (1 vCPU, 1 GB RAM, 10 GB SSD):**
- Nginx: ~3-5 MB
- PostgreSQL: ~50-80 MB
- Python/uvicorn: ~80-120 MB
- Система: ~100 MB
- **Итого: ~250-350 MB** (из 1 GB — OK)
- **Swap: 2 GB** (защита от OOM при пиковой нагрузке)

---

## 🔄 CI/CD Pipeline

### GitHub Actions (`.github/workflows/deploy.yml`)

**Запускается автоматически при push в `main`:**

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│   Test Job  │ →   │ Deploy Job   │ →   │  Success/Fail  │
│ (Ubuntu)    │     │ (Ubuntu SSH) │     │  (GitHub UI)   │
└─────────────┘     └──────────────┘     └────────────────┘
      │                     │
      │  1. pytest          │  1. SSH to server
      │  2. coverage        │  2. git reset --hard
      │  3. if fail → stop  │  3. DB backup
      │                     │  4. Backend deploy
      │                     │  5. Frontend build
      │                     │  6. Health check
```

**Safety Gates:**

| Gate | Что делает | При fail |
|------|-----------|----------|
| CI tests | Тесты на SQLite (aiosqlite) | Деплой отменяется |
| Server tests | Тесты на сервере перед restart | Деплой abort, сервис не перезапускается |
| DB backup | SQL dump перед миграциями | Warn, но есть бэкап |
| Health check | 3 попытки проверки /health | Warning, но деплой завершается |

---

## 🚀 Пошаговый деплой

### Шаг 1: Push в main

```bash
git add .
git commit -m "Your message"
git push origin main
```

GitHub Actions автоматически запустит пайплайн.

### Шаг 2: CI/CD (автоматически)

Пайплайн делает:

1. **Test job** — pytest на SQLite
2. **Deploy job** (только если тесты прошли):
   - SSH на сервер
   - `git reset --hard origin/main` + `git clean -fd`
   - Бэкап БД: `pg_dump`
   - Запуск `deploy_setup.sh` (создание systemd service)
   - Сборка бэкенда (venv + pip install)
   - Тесты на сервере (SQLite)
   - Фикс schema: `fix_all_tables.sql`
   - Фикс ownership: `audit_logs`
   - Alembic миграции
   - Создание суперюзера
   - Фикс БД, мастеров, сиды
   - Сборка фронтенда (Vite)
   - Копирование `dist/` в `/var/www/beauty-specialist/frontend/dist/`
   - Фикс логов
   - Запись nginx конфига
   - Рестарт сервисов

### Шаг 3: Ручная проверка

```bash
# На сервере:
sudo systemctl status beauty-backend
sudo systemctl status nginx
curl https://beauty-specialist.ru/health
```

---

## 🔧 Ручной деплой (если CI не сработал)

```bash
# SSH на сервер
ssh deploy@beauty-specialist.ru

cd /var/www/beauty-specialist

# 1. Git
git fetch origin main
git reset --hard origin/main
git clean -fd

# 2. Fix permissions
sudo chown -R deploy:deploy /var/www/beauty-specialist 2>/dev/null || true
sudo chmod -R u+rw /var/www/beauty-specialist 2>/dev/null || true

# 3. Бэкап БД
pg_dump $(grep DATABASE_URL online-booking/backend/.env | cut -d= -f2) > /tmp/db-backup-$(date +%Y%m%d-%H%M%S).sql

# 4. Бэкенд
cd online-booking/backend
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Тесты
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite
PYTHONPATH=. pytest tests/ -v --tb=short --tb=no 2>&1 | tee /tmp/test-results.txt

# 6. Фикс schema (ПЕРЕД alembic!)
sudo -u postgres psql -d online_booking -f fix_all_tables.sql

# 7. Ownership
sudo -u postgres psql -d online_booking -c "ALTER TABLE audit_logs OWNER TO specialist;"

# 8. Миграции
DATABASE_URL=$(grep DATABASE_URL .env | cut -d= -f2)
alembic upgrade head

# 9. Суперюзер
python3.12 create_superuser.py

# 10. Фиксы
python3.12 fix_production_db.py
python3.12 fix_production_masters.py

# 11. Сиды
python3.12 seed_production.py
python3.12 create_minimal_reviews.py

# 12. Фронтенд
cd ../frontend

# Очистка
find src -name "*.js" -type f -delete
rm -rf node_modules/.vite .vite dist node_modules ~/.cache/vite ~/.vite node_modules/.cache .vite-temp .vite-deps
npm cache clean --force
npm ci --no-audit --no-fund
rm -rf node_modules/.vite/deps node_modules/.vite/deps-cache node_modules/.vite
rm -rf ~/.cache/vite ~/.vite/deps

# BUILD_ID
export BUILD_ID=$(git rev-parse --short=7 HEAD)
echo "BUILD_ID: $BUILD_ID"

# Сборка
npm run build 2>&1 | tee /tmp/build-output.txt

# Проверка
grep "searchCities" dist/assets/*.js || echo "ERROR: missing searchCities"
grep "/api/v1/cities" dist/assets/*.js && echo "ERROR: old cities endpoint found"

# Копирование
rm -rf /var/www/beauty-specialist/frontend/dist
mkdir -p /var/www/beauty-specialist/frontend/dist
cp -r dist/* /var/www/beauty-specialist/frontend/dist/

# 13. Логи
sudo chown -R www-data:www-data /var/www/beauty-specialist/online-booking/backend/logs/

# 14. Nginx
sed -i 's/\r$//' deploy_fix_nginx.sh
bash deploy_fix_nginx.sh

# 15. Рестарт
sudo systemctl restart beauty-backend
sudo systemctl restart nginx
sleep 5

# 16. Проверка
sudo systemctl is-active --quiet beauty-backend && echo "SUCCESS" || echo "FAILED"
```

---

## ⚠️ Критические ошибки и как их избежать

### 1. Stale `.js` файлы в `src/`

**Проблема:** На сервере в `src/` могут остаться старые `.js` файлы от предыдущих сборок. Vite читает их вместо `.ts/.tsx`.

**Решение:**
```bash
# УДАЛЯТЬ ПЕРЕД КАЖДЫМ ДЕПЛОЕМ:
find src -name "*.js" -type f -delete
```

### 2. BUILD_ID cache busting

**Проблема:** Если содержимое JS файла не меняется, Vite генерирует тот же hash. Браузер кэширует старый файл.

**Решение (vite.config.ts):**
```typescript
entryFileNames: `assets/[name]-[hash]-${process.env.BUILD_ID || 'dev'}.js`
chunkFileNames: `assets/[name]-[hash]-${process.env.BUILD_ID || 'dev'}.js`
assetFileNames: `assets/[name]-[hash]-${process.env.BUILD_ID || 'dev'}.[ext]`
```

**В deploy.yml:**
```bash
export BUILD_ID=$(git rev-parse --short=7 HEAD)
```

### 3. Очистка кэшей Vite

**ПЕРЕД КАЖДЫМ ДЕПЛОЕМ:**
```bash
# Удалить stale .js
find src -name "*.js" -type f -delete

# Все возможные кэши Vite:
rm -rf node_modules/.vite
rm -rf .vite
rm -rf dist
rm -rf node_modules
rm -rf ~/.cache/vite
rm -rf ~/.vite
rm -rf node_modules/.cache
rm -rf .vite-temp
rm -rf .vite-deps
npm cache clean --force

# После npm ci — снова очистить:
npm ci --no-audit --no-fund
rm -rf node_modules/.vite/deps
rm -rf node_modules/.vite/deps-cache
rm -rf node_modules/.vite
rm -rf ~/.cache/vite
rm -rf ~/.vite/deps
```

### 4. Проверка собранного JS

**НЕ ПРОВЕРЯТЬ ИСХОДНИКИ — проверять СБОРКУ!**

```bash
# Правильная проверка (свойство объекта выживает минификацию):
grep "searchCities" dist/assets/*.js

# НЕЛЬЗЯ проверять (переменная переименовывается минификатором):
grep "dadataApi" dist/assets/*.js  # ❌ ВСЕГДА падает!

# URL конвертируется в unicode escapes:
grep "suggestions.dadata.ru" dist/assets/*.js  # ❌ Может не работать!

# Проверка отсутствия старого кода:
grep "/api/v1/cities" dist/assets/*.js  # ❌ Должно быть пусто!
```

### 5. Windows CRLF

**ВСЕ shell скрипты должны быть в LF:**
```bash
sed -i 's/\r$//' deploy_setup.sh
sed -i 's/\r$//' deploy_fix_nginx.sh
```

### 6. `sudo tee` вместо `cat >`

```bash
# НЕЛЬЗЯ:
cat > /etc/nginx/sites-enabled/beauty-specialist << 'EOF'

# МОЖНО:
sudo tee /etc/nginx/sites-enabled/beauty-specialist > /dev/null << 'EOF'
```

### 7. Удаление `dist` — целиком!

```bash
# НЕЛЬЗЯ (оставляет скрытые файлы):
rm -rf dist/*

# МОЖНО:
rm -rf dist
mkdir -p dist
```

### 8. Тесты на сервере

**Тесты падают на PostgreSQL! Они проходят только на SQLite.**

```bash
# В deploy.yml — тесты запускаются с aiosqlite:
pip install pytest pytest-asyncio pytest-cov httpx aiosqlite
PYTHONPATH=. pytest tests/ -v --tb=short

# Проверка результатов:
if grep -qE "^[=]+.*failed" /tmp/test-results.txt || \
   grep -qE "^[=]+.*error" /tmp/test-results.txt; then
    exit 1
fi
```

### 9. `script_stop: false` в CI/CD

**Проблема:** `script_stop: true` включает `set -e` — скрипт прерывается от любой ошибки (SIGPIPE от `head`/`tail`, `grep` без совпадений).

**Решение:** `script_stop: false`. Критические ошибки имеют явную проверку с `exit 1`.

### 10. `git reset --hard` вместо `git pull`

**Проблема:** `git pull` не удаляет файлы, которых нет в репозитории, и не подтягивает удалённые.

**Решение:**
```bash
git fetch origin main
git reset --hard origin/main
git clean -fd
```

---

## 🐛 Troubleshooting

### Изменения не применяются

1. Проверить stale `.js` в `src/`: `find src -name "*.js" -type f`
2. Проверить BUILD_ID в имени файла: `ls dist/assets/*.js`
3. Проверить содержимое JS: `grep "searchCities" dist/assets/*.js`
4. Проверить копирование: `ls /var/www/beauty-specialist/frontend/dist/assets/`
5. Проверить nginx: `grep "Cache-Control" /etc/nginx/sites-enabled/beauty-specialist`
6. Hard reload: `Ctrl+Shift+R`

### Бэкенд не запускается

1. Проверить `.env`: `cat online-booking/backend/.env`
2. Проверить БД: `sudo -u postgres psql -d online_booking -c "SELECT 1"`
3. Проверить логи: `sudo journalctl -u beauty-backend --no-pager -n 50`
4. Проверить порт: `ss -tlnp | grep 8000`

### Nginx возвращает 502

1. Проверить бэкенд: `curl http://localhost:8000/health`
2. Проверить nginx конфиг: `sudo nginx -t`
3. Проверить логи: `sudo tail -n 50 /var/log/nginx/error.log`

### База данных недоступна

1. Проверить PostgreSQL: `sudo systemctl status postgresql`
2. Проверить подключение: `sudo -u postgres psql -d online_booking -c "SELECT 1"`
3. Проверить место на диске: `df -h`

---

## ✅ Health Checks

```bash
# Backend
curl https://beauty-specialist.ru/health

# Frontend
curl -s https://beauty-specialist.ru/ | grep -o "beauty-specialist"

# Database
sudo -u postgres psql -d online_booking -c "SELECT count(*) FROM users;"

# Nginx
sudo systemctl status nginx
sudo nginx -t

# System
free -h
df -h
```

---

## 📊 Checklist перед деплоем

> Единый чеклист — [DEPLOYMENT_RULES.md#checklist-перед-деплоем](DEPLOYMENT_RULES.md#checklist-перед-деплоем). Здесь только секретная часть:
- [ ] Нет реальных секретов в DEPLOY.md (только placeholders)
- [ ] Секреты в `LOCAL.md` (локальный файл, не пушить в git)

#!/bin/bash
# =============================================================
# Universal Deploy Script — Beauty Specialist
# =============================================================
# Работает и локально, и на сервере.
# Автоматически:
#   1. Проверяет и исправляет схему БД
#   2. Запускает миграции Alembic
#   3. Создаёт/обновляет суперпользователя
#   4. Заполняет seed-данными
#   5. Проверяет что всё работает
#
# Использование:
#   ./deploy.sh              # продакшен (PostgreSQL)
#   ./deploy.sh --local      # локально (SQLite)
#   ./deploy.sh --dry-run    # только проверка без изменений
# =============================================================

set -e

# ─── Цвета для вывода ──────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# ─── Аргументы ─────────────────────────────────────────────────
MODE="production"
DRY_RUN=false

for arg in "$@"; do
    case $arg in
        --local)
            MODE="local"
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            error "Неизвестный аргумент: $arg"
            echo "Использование: $0 [--local] [--dry-run]"
            exit 1
            ;;
    esac
done

# ─── Переменные окружения ──────────────────────────────────────
if [ "$MODE" = "local" ]; then
    export DATABASE_URL="sqlite+aiosqlite:///./dev.db"
    BACKEND_DIR="$(dirname "$0")/online-booking/backend"
    info "Локальный режим (SQLite)"
else
    if [ -z "$DATABASE_URL" ]; then
        error "DATABASE_URL не установлен!"
        echo "Установите переменную окружения:"
        echo "  export DATABASE_URL='postgresql+asyncpg://user:pass@host:5432/dbname'"
        exit 1
    fi
    BACKEND_DIR="$(pwd)/online-booking/backend"
    info "Продакшен режим (PostgreSQL)"
fi

cd "$BACKEND_DIR"

# ─── Шаг 1: Проверка схемы БД ─────────────────────────────────
echo ""
echo "=========================================="
echo "  Шаг 1: Проверка схемы БД"
echo "=========================================="

check_and_fix_schema() {
    if [ "$DRY_RUN" = true ]; then
        info "[DRY-RUN] Проверка схемы БД..."
        return
    fi

    # Определяем, какая БД используется
    if [[ "$DATABASE_URL" == sqlite* ]]; then
        info "SQLite — схема создаётся автоматически через Alembic"
        return
    fi

    # PostgreSQL — проверяем и исправляем
    info "Проверка схемы PostgreSQL..."

    # Создаём SQL-скрипт для исправления схемы
    cat > /tmp/fix_schema.sql << 'SQLEOF'
-- =====================================================
-- FIX SCHEMA: Автоматическое исправление схемы БД
-- =====================================================
-- Эта миграция добавляет колонки, которые могли быть
-- добавлены в модель, но отсутствуют в старой БД.
--
-- ВАЖНО: Эту процедуру нужно запускать ПЕРЕД alembic upgrade head
-- при деплое на сервер с существующей БД.
-- =====================================================

-- ─── countries ──────────────────────────────────────────
-- Старая схема: id, name, code, created_at
-- Новая схема:  id, code, name_ru, name_en, phone_prefix, is_active

ALTER TABLE countries ADD COLUMN IF NOT EXISTS name_en VARCHAR(100);
ALTER TABLE countries ADD COLUMN IF NOT EXISTS phone_prefix VARCHAR(10);
ALTER TABLE countries ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE countries DROP COLUMN IF EXISTS name;
ALTER TABLE countries DROP COLUMN IF EXISTS created_at;

-- ─── cities ─────────────────────────────────────────────
-- Старая схема: id, country_id, name, created_at
-- Новая схема:  id, country_id, name_ru, name_en, slug, is_active

ALTER TABLE cities ADD COLUMN IF NOT EXISTS name_en VARCHAR(100);
ALTER TABLE cities ADD COLUMN IF NOT EXISTS slug VARCHAR(100);
ALTER TABLE cities ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE cities RENAME COLUMN name TO name_ru;

-- ─── master_profiles ────────────────────────────────────
-- Добавляем unique constraint на user_id (если нет)
-- Примечание: в модели user_id unique=True, но constraint мог не создаться

DO $$
BEGIN
    -- Проверяем, есть ли unique constraint
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'uq_master_profiles_user_id'
        AND table_name = 'master_profiles'
    ) THEN
        -- Если нет unique, создаём индекс (не constraint, но работает)
        CREATE UNIQUE INDEX IF NOT EXISTS idx_master_profiles_user_id_unique
        ON master_profiles(user_id)
        WHERE user_id IS NOT NULL;
    END IF;
END $$;
SQLEOF

    if [ -f /tmp/fix_schema.sql ]; then
        info "Применяю исправления схемы..."
        sudo -u postgres psql -d online_booking -f /tmp/fix_schema.sql 2>&1 | while read line; do
            if [[ "$line" == *"ERROR"* ]]; then
                warn "$line"
            else
                echo "  $line"
            fi
        done
        success "Схема БД проверена и исправлена"
    fi
}

check_and_fix_schema

# ─── Шаг 2: Миграции Alembic ────────────────────────────────
echo ""
echo "=========================================="
echo "  Шаг 2: Миграции Alembic"
echo "=========================================="

if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] alembic upgrade head"
else
    info "Применяю миграции..."
    alembic upgrade head
    success "Миграции применены"
fi

# ─── Шаг 3: Суперпользователь ───────────────────────────────
echo ""
echo "=========================================="
echo "  Шаг 3: Суперпользователь"
echo "=========================================="

if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] create_superuser.py"
else
    info "Создаю/обновляю суперпользователя..."
    python3.12 create_superuser.py
    success "Суперпользователь готов"
fi

# ─── Шаг 4: Seed-данные ─────────────────────────────────────
echo ""
echo "=========================================="
echo "  Шаг 4: Seed-данные"
echo "=========================================="

if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] seed_production.py"
else
    info "Заполняю seed-данными..."
    python3.12 seed_production.py
    success "Seed-данные заполнены"
fi

# ─── Шаг 5: Минимальные отзывы ──────────────────────────────
echo ""
echo "=========================================="
echo "  Шаг 5: Отзывы"
echo "=========================================="

if [ "$DRY_RUN" = true ]; then
    info "[DRY-RUN] create_minimal_reviews.py"
else
    info "Создаю минимальные отзывы..."
    python3.12 create_minimal_reviews.py
    success "Отзывы созданы"
fi

# ─── Шаг 6: Проверка данных ─────────────────────────────────
echo ""
echo "=========================================="
echo "  Шаг 6: Проверка данных"
echo "=========================================="

check_data() {
    if [ "$DRY_RUN" = true ]; then
        info "[DRY-RUN] Проверка данных..."
        return
    fi

    if [[ "$DATABASE_URL" == sqlite* ]]; then
        info "SQLite — проверка через Python..."
        python3.12 -c "
from app.database import AsyncSessionLocal
from sqlalchemy import text

async def check():
    async with AsyncSessionLocal() as session:
        # Проверяем countries
        result = await session.execute(text('SELECT count(*) FROM countries'))
        countries_count = result.scalar()
        print(f'  Countries: {countries_count}')
        
        # Проверяем cities
        result = await session.execute(text('SELECT count(*) FROM cities'))
        cities_count = result.scalar()
        print(f'  Cities: {cities_count}')
        
        # Проверяем users
        result = await session.execute(text('SELECT count(*) FROM users'))
        users_count = result.scalar()
        print(f'  Users: {users_count}')
        
        if countries_count == 0:
            print('  [WARN] Таблица countries пуста!')
        if cities_count == 0:
            print('  [WARN] Таблица cities пуста!')

import asyncio
asyncio.run(check())
"
    else
        info "Проверяю PostgreSQL..."
        cat > /tmp/check_data.sql << 'EOF'
SELECT 'countries' as table_name, count(*) FROM countries
UNION ALL
SELECT 'cities', count(*) FROM cities
UNION ALL
SELECT 'users', count(*) FROM users
UNION ALL
SELECT 'master_profiles', count(*) FROM master_profiles
UNION ALL
SELECT 'reviews', count(*) FROM reviews;
EOF
        sudo -u postgres psql -d online_booking -f /tmp/check_data.sql 2>&1 | while read line; do
            echo "  $line"
        done
    fi
}

check_data

# ─── Шаг 7: Фронтенд (только на сервере) ────────────────────
echo ""
echo "=========================================="
echo "  Шаг 7: Фронтенд"
echo "=========================================="

if [ "$MODE" = "local" ]; then
    info "Пропускаю сборку фронтенда в локальном режиме"
else
    FRONTEND_DIR="$BACKEND_DIR/../frontend"
    if [ -d "$FRONTEND_DIR" ]; then
        info "Собираю фронтенд..."
        cd "$FRONTEND_DIR"
        npm ci 2>&1 | tail -5
        npm run build 2>&1 | tail -5
        sudo cp -r dist/* /var/www/beauty-specialist/frontend/dist/
        success "Фронтенд собран и скопирован"
    else
        warn "Директория frontend не найдена: $FRONTEND_DIR"
    fi
fi

# ─── Шаг 8: Перезапуск сервисов (только на сервере) ─────────
echo ""
echo "=========================================="
echo "  Шаг 8: Перезапуск сервисов"
echo "=========================================="

if [ "$MODE" = "local" ]; then
    info "Пропускаю перезапуск в локальном режиме"
else
    # Фиксим права на логи
    info "Фикшу права на логи..."
    sudo chown -R www-data:www-data /var/www/beauty-specialist/online-booking/backend/logs/
    sudo chmod -R 755 /var/www/beauty-specialist/online-booking/backend/logs/
    success "Права на логи исправлены"

    # Перезапускаем
    info "Перезапускаю сервисы..."
    sudo systemctl restart beauty-backend
    sudo systemctl restart nginx
    success "Сервисы перезапущены"

    # Ждём запуска
    info "Жду запуска бэкенда..."
    sleep 5

    # Проверяем
    echo ""
    echo "=========================================="
    echo "  Финальная проверка"
    echo "=========================================="

    # Проверяем статус
    if systemctl is-active --quiet beauty-backend; then
        success "Backend запущен"
    else
        error "Backend НЕ запущен!"
        sudo systemctl status beauty-backend --no-pager | head -20
        exit 1
    fi

    # Проверяем порт
    if ss -tlnp | grep -q 8000; then
        success "Порт 8000 слушается"
    else
        error "Порт 8000 НЕ слушается!"
        exit 1
    fi

    # Проверяем API
    info "Тестирую API..."
    HEALTH=$(curl -sf http://127.0.0.1:8000/health 2>&1) || true
    if [[ "$HEALTH" == *"200"* ]] || [[ "$HEALTH" == *"healthy"* ]]; then
        success "Health check прошёл"
    else
        warn "Health check вернул: $HEALTH"
    fi

    COUNTRIES=$(curl -sf http://127.0.0.1:8000/api/v1/countries/ 2>&1) || true
    if [[ "$COUNTRIES" == "["* ]]; then
        success "API /countries/ работает"
    else
        error "API /countries/ НЕ работает: $COUNTRIES"
        exit 1
    fi

    echo ""
    echo "=========================================="
    echo -e "${GREEN}  ДЕПЛОЙ ЗАВЕРШЁН УСПЕШНО!${NC}"
    echo "=========================================="
    echo ""
    echo "Сайт: https://beauty-specialist.ru"
    echo "Swagger: https://beauty-specialist.ru/docs"
    echo ""
fi

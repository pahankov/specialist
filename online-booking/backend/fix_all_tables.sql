-- =============================================================
-- COMPREHENSIVE SCHEMA FIX — Beauty Specialist Production DB
-- =============================================================
-- ЭТОТ СКРИПТ ДОЛЖЕН ЗАПУСКАТЬСЯ ПЕРЕЖДЕМ alembic upgrade head
-- на любом сервере с существующей БД.
--
-- Он добавляет ВСЕ недостающие колонки из моделей SQLAlchemy.
-- Idempotent — безопасен для многократного запуска.
--
-- Использование:
--   sudo -u postgres psql -d online_booking -f fix_all_tables.sql
-- =============================================================

-- =============================================================
-- 1. refresh_tokens
-- =============================================================
-- Модель: id, user_id, token, expires_at, is_revoked, revoked_at, created_at
ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS is_revoked BOOLEAN DEFAULT FALSE NOT NULL;
ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMP WITH TIME ZONE;

-- =============================================================
-- 2. countries
-- =============================================================
-- Модель: id, code, name_ru, name_en, phone_prefix, is_active
ALTER TABLE countries ADD COLUMN IF NOT EXISTS name_en VARCHAR(100);
ALTER TABLE countries ADD COLUMN IF NOT EXISTS phone_prefix VARCHAR(10);
ALTER TABLE countries ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE countries DROP COLUMN IF EXISTS name;
ALTER TABLE countries DROP COLUMN IF EXISTS created_at;

-- =============================================================
-- 3. cities
-- =============================================================
-- Модель: id, country_id, name_ru, name_en, slug, is_active
ALTER TABLE cities ADD COLUMN IF NOT EXISTS name_en VARCHAR(100);
ALTER TABLE cities ADD COLUMN IF NOT EXISTS slug VARCHAR(100);
ALTER TABLE cities ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE cities RENAME COLUMN name TO name_ru;

-- =============================================================
-- 4. users (проверка)
-- =============================================================
-- Модель: id, email, phone, hashed_password, name, role, city_id, is_active, is_verified, created_at, updated_at
-- Должна быть в порядке, но проверим
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_verified BOOLEAN DEFAULT FALSE;

-- =============================================================
-- 5. master_profiles — fix enum values
-- =============================================================
-- Модель: status uses MasterStatus.ACTIVE = "active"
-- Но в БД enum type может быть создан с uppercase значениями
-- Нужно привести enum к lowercase значениям модели

-- Сначала исправляем данные (преобразуем uppercase в lowercase)
UPDATE master_profiles SET status = 'active' WHERE status = 'ACTIVE';
UPDATE master_profiles SET status = 'inactive' WHERE status = 'INACTIVE';
UPDATE master_profiles SET status = 'suspended' WHERE status = 'SUSPENDED';

-- Удаляем старый enum type БЕЗ CASCADE (чтобы не удалить колонку!)
DROP TYPE IF EXISTS masterstatus;

-- Создаём новый с lowercase значениями как в модели
CREATE TYPE masterstatus AS ENUM ('active', 'inactive', 'suspended');

-- Alter the column to use the new type (drop default first)
ALTER TABLE master_profiles ALTER COLUMN status DROP DEFAULT;
ALTER TABLE master_profiles ALTER COLUMN status TYPE masterstatus USING status::text::masterstatus;
ALTER TABLE master_profiles ALTER COLUMN status SET DEFAULT 'active'::masterstatus;

-- =============================================================
-- 6. client_profiles
-- =============================================================
-- Модель: id, user_id, no_show_count, preferred_service_ids, created_at, updated_at
ALTER TABLE client_profiles ADD COLUMN IF NOT EXISTS no_show_count INTEGER DEFAULT 0;
ALTER TABLE client_profiles ADD COLUMN IF NOT EXISTS preferred_service_ids JSON;

-- =============================================================
-- 7. services
-- =============================================================
-- Модель: id, master_id, name, description, duration_minutes, price, is_active, created_at, updated_at
ALTER TABLE services ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- =============================================================
-- 8. appointments
-- =============================================================
-- Модель: id, master_id, service_id, client_id, appointment_date, status, notes, created_at, updated_at
-- client_id в старой БД мог быть user_id вместо client_id
-- Проверим и исправим если нужно

-- =============================================================
-- 9. reviews
-- =============================================================
-- Модель: id, appointment_id, master_id, client_name, client_phone, rating, comment, is_published, created_at
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS is_published BOOLEAN DEFAULT TRUE;

-- =============================================================
-- 10. working_hours
-- =============================================================
-- Модель: id, master_id, day_of_week, start_time, end_time, is_active, created_at, updated_at
ALTER TABLE working_hours ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;

-- =============================================================
-- 11. audit_logs
-- =============================================================
-- Модель: id, user_id, master_id, action, details, created_at
-- Должна быть в порядке

-- =============================================================
-- 12. blocked_slots
-- =============================================================
-- Модель: id, master_id, start_time, end_time, reason, created_at
-- Должна быть в порядке

-- =============================================================
-- 13. otp_codes
-- =============================================================
-- Модель: id, user_id, phone, code, expires_at, is_used, created_at
ALTER TABLE otp_codes ADD COLUMN IF NOT EXISTS is_used BOOLEAN DEFAULT FALSE;

-- =============================================================
-- 14. fill missing data (countries, cities)
-- =============================================================

-- Countries
INSERT INTO countries (code, name_ru, name_en, phone_prefix, is_active)
SELECT 'RU', 'Россия', 'Russia', '+7', TRUE
WHERE NOT EXISTS (SELECT 1 FROM countries WHERE code = 'RU');

INSERT INTO countries (code, name_ru, name_en, phone_prefix, is_active)
SELECT 'KZ', 'Казахстан', 'Kazakhstan', '+7', TRUE
WHERE NOT EXISTS (SELECT 1 FROM countries WHERE code = 'KZ');

INSERT INTO countries (code, name_ru, name_en, phone_prefix, is_active)
SELECT 'BY', 'Беларусь', 'Belarus', '+375', TRUE
WHERE NOT EXISTS (SELECT 1 FROM countries WHERE code = 'BY');

-- Cities for Russia
INSERT INTO cities (country_id, name_ru, name_en, slug, is_active)
SELECT c.id, city_name, city_name, LOWER(REPLACE(city_name, ' ', '-')), TRUE
FROM countries c,
     unnest(ARRAY[
       'Москва', 'Санкт-Петербург', 'Новосибирск', 'Екатеринбург',
       'Казань', 'Нижний Новгород', 'Челябинск', 'Самара',
       'Омск', 'Ростов-на-Дону', 'Уфа', 'Красноярск',
       'Воронеж', 'Пермь', 'Волгоград'
     ]) AS city_name
WHERE c.code = 'RU'
AND NOT EXISTS (
  SELECT 1 FROM cities ci WHERE ci.name_ru = city_name AND ci.country_id = c.id
);

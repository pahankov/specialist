# Database Documentation — beauty-specialist.ru

> Полная документация по базе данных PostgreSQL 16.
> Включает: схему, миграции, ошибки и как их избежать.

---

## Содержание

- [Обзор](# обзор)
- [Таблицы](#таблицы)
- [Связи (Relationships)](#связи-relationships)
- [Миграции Alembic](#миграции-alembic)
- [Частые ошибки БД и как их избежать](#частые-ошибки-бд-и-как-их-избежать)
- [Ручные запросы](#ручные-запросы)
- [Бэкапы](#бекапы)

---

## Обзор

**База данных:** PostgreSQL 16
**Имя БД:** `online_booking`
**Пользователь:** `specialist`
**ORM:** SQLAlchemy 2.0 (async)
**Миграции:** Alembic

**Стек:**
- Драйвер: `asyncpg` для async, `psycopg2` для миграций
- Сессия: `AsyncSession` с `expire_on_commit=False`
- Engine: `create_async_engine` с `pool_size`, `max_overflow`

---

## Таблицы

### 1. users

**Назначение:** Основные пользователи системы (клиенты, мастера, админы)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| email | VARCHAR(255) | UNIQUE, NULLABLE | Email (для login по email) |
| phone | VARCHAR(20) | UNIQUE, NULLABLE | Телефон (для login по SMS) |
| hashed_password | VARCHAR(255) | NULLABLE | NULL для OTP-only клиентов |
| name | VARCHAR(100) | NOT NULL | Имя пользователя |
| role | ENUM | NOT NULL, DEFAULT CLIENT | CLIENT, MASTER, ADMIN |
| city_id | INTEGER | FK -> cities.id, NULLABLE | Город пользователя |
| is_active | BOOLEAN | DEFAULT TRUE | Мягкое удаление |
| is_verified | BOOLEAN | DEFAULT FALSE | Верификация (email/phone) |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

**Индексы:** `ix_users_email` (UNIQUE), `ix_users_phone` (UNIQUE), `ix_users_role`

**Enums (UserRole):**
- `CLIENT` — обычный пользователь
- `MASTER` — мастер (услуга)
- `ADMIN` — супер-админ (управление)

### 2. client_profiles

**Назначение:** Дополнительно profiles для клиентов

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| user_id | INTEGER | UNIQUE, NOT NULL, FK -> users.id ON DELETE CASCADE | Ссылка на users.id |
| no_show_count | INTEGER | DEFAULT 0 | Количество no-show |
| preferred_service_ids | JSON | NULLABLE | Список предпочтительных услуг |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

### 3. master_profiles

**Назначение:** Profiles мастеров (услуг)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| user_id | INTEGER | UNIQUE, NOT NULL, FK -> users.id ON DELETE CASCADE | Ссылка на users.id |
| description | TEXT | NULLABLE | Описание мастера |
| avatar_url | VARCHAR(500) | NULLABLE | URL аватара |
| telegram_username | VARCHAR(100) | NULLABLE | Telegram username |
| experience_years | INTEGER | NULLABLE | Опыт работы (лет) |
| status | VARCHAR(20) | NOT NULL, DEFAULT active | active, inactive, suspended |
| is_active | BOOLEAN | DEFAULT TRUE | Мягкое удаление |
| tariff | VARCHAR(20) | NOT NULL, DEFAULT trial | Тариф (фундамент биллинга, пока всем trial) |
| trial_ends_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Конец триала (новым: +180 дней) |
| work_start_hour | INTEGER | NOT NULL, DEFAULT 8 | Начало дневного окна (границы гранул расписания) |
| work_end_hour | INTEGER | NOT NULL, DEFAULT 22 | Конец дневного окна (границы гранул расписания) |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

**Важно:** Супер-админ (ADMIN) НЕ имеет MasterProfile! `master_profiles` = NULL для role=ADMIN.

**Правило active:** `status=active` ⟺ есть ≥1 активного рабочего дня с `schedule_date >= сегодня`
(прошлое не считается; `suspended` правилом не трогается). Пересчёт — в CRUD
рабочих часов (create/update/delete/toggle), см. `services/master_status.py`.

### 4. appointments

**Назначение:** Записи на приём

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | ID мастера |
| service_id | INTEGER | NOT NULL, FK -> services.id ON DELETE CASCADE | ID услуги |
| client_id | INTEGER | NOT NULL, FK -> client_profiles.id ON DELETE CASCADE | ID клиента |
| appointment_date | TIMESTAMP WITH TIME ZONE | NOT NULL | Дата и время записи |
| status | VARCHAR(20) | DEFAULT pending | pending, confirmed, completed, cancelled, no_show |
| notes | TEXT | NULLABLE | Примечания |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

**Индексы:** `ix_appointments_master_status`, `ix_appointments_master_date`

### 5. services

**Назначение:** Услуги мастеров

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | ID мастера |
| name | VARCHAR(200) | NOT NULL | Название услуги |
| description | TEXT | NULLABLE | Описание |
| duration_minutes | INTEGER | NOT NULL | Длительность (минуты) |
| price | NUMERIC(10, 2) | NOT NULL | Цена |
| is_active | BOOLEAN | DEFAULT TRUE | Активна ли |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

### 6. working_hours

**Назначение:** Рабочие часы мастеров

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | ID мастера |
| schedule_date | DATE | NOT NULL | Дата |
| start_time | TIME | NOT NULL | Начало (использовать datetime.time, не строку!) |
| end_time | TIME | NOT NULL | Конец |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Активна ли |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

**Важно:** `start_time` и `end_time` — `Column(Time)`. Используйте `datetime.time(9, 0)`, НЕ строку `"09:00:00"`!

### 7. cities

**Назначение:** Города

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| country_id | INTEGER | NOT NULL, FK -> countries.id ON DELETE CASCADE | ID страны |
| name_ru | VARCHAR(200) | NOT NULL | Название на русском |
| name_en | VARCHAR(200) | NULLABLE | Название на английском |
| slug | VARCHAR(200) | NOT NULL | URL-friendly slug |
| is_active | BOOLEAN | DEFAULT TRUE | Активен ли |

**Индексы:** `ix_cities_country_slug` (country_id, slug, UNIQUE)

### 8. countries

**Назначение:** Страны

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| code | VARCHAR(3) | NOT NULL, UNIQUE | ISO 3166-1 alpha-2 |
| name_ru | VARCHAR(100) | NOT NULL | Название на русском |
| name_en | VARCHAR(100) | NOT NULL | Название на английском |
| phone_prefix | VARCHAR(10) | NOT NULL | Телефонный код (например, "+7") |
| is_active | BOOLEAN | DEFAULT TRUE | Активна ли |

### 9. reviews

**Назначение:** Отзывы клиентов

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| appointment_id | INTEGER | UNIQUE, NOT NULL, FK -> appointments.id ON DELETE CASCADE | ID записи |
| master_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | ID мастера |
| client_name | VARCHAR(100) | NOT NULL | Имя клиента |
| client_phone | VARCHAR(20) | NOT NULL | Телефон клиента |
| rating | FLOAT | NOT NULL | Рейтинг (1-5) |
| comment | TEXT | NULLABLE | Комментарий |
| is_published | BOOLEAN | DEFAULT FALSE | Опубликован ли |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |

### 10. refresh_tokens

**Назначение:** JWT refresh токены

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| user_id | INTEGER | NOT NULL, FK -> users.id ON DELETE CASCADE | ID пользователя |
| token | VARCHAR(512) | NOT NULL, UNIQUE | Хэш токена |
| expires_at | TIMESTAMP WITH TIME ZONE | NOT NULL | Срок действия |
| is_revoked | BOOLEAN | DEFAULT FALSE | Отозван ли |
| revoked_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Время отзыва |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |

**Важно:** `expires_at` — `DateTime(timezone=True)`. Всегда используйте timezone-aware datetime для сравнения!

### 11. audit_logs

**Назначение:** Логи действий (аудит)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_id | INTEGER | FK -> users.id ON DELETE SET NULL | ID пользователя (не master_profiles!) |
| level | VARCHAR(10) | NOT NULL, DEFAULT info | info, warning, error |
| action | VARCHAR(50) | NOT NULL | Действие (create, update, delete) |
| entity_type | VARCHAR(50) | NOT NULL | Тип сущности (user, service, appointment) |
| entity_id | INTEGER | NULLABLE | ID сущности |
| details | TEXT | NULLABLE | Детали |
| ip_address | VARCHAR(45) | NULLABLE | IP адрес |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |

**Важно:** FK идёт на `users.id`, а НЕ на `master_profiles.id`!

### 12. blocked_slots

**Назначение:** Заблокированные временные слоты

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | ID мастера |
| start_dt | TIMESTAMP WITH TIME ZONE | NOT NULL | Начало |
| end_dt | TIMESTAMP WITH TIME ZONE | NOT NULL | Конец |
| reason | TEXT | NULLABLE | Причина |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

### 13. otp_codes

**Назначение:** OTP коды для SMS-авторизации

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| phone | VARCHAR(20) | NOT NULL | Телефон |
| code_hash | VARCHAR(255) | NOT NULL | Хэш кода |
| expires_at | TIMESTAMP WITH TIME ZONE | NOT NULL | Срок действия |
| is_used | BOOLEAN | DEFAULT FALSE | Использован ли |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |

---

## Связи (Relationships)

### 1:N (One-to-Many)

| Родитель | Ребёнок | Тип | ON DELETE |
|----------|---------|-----|-----------|
| users | client_profiles | 1:1 (unique) | CASCADE |
| users | master_profiles | 1:1 (unique) | CASCADE |
| master_profiles | services | 1:N | CASCADE |
| master_profiles | working_hours | 1:N | CASCADE |
| master_profiles | blocked_slots | 1:N | CASCADE |
| master_profiles | reviews | 1:N | CASCADE |
| users | refresh_tokens | 1:N | CASCADE |
| cities | users | 1:N | SET NULL |
| countries | cities | 1:N | CASCADE |
| appointments | reviews | 1:1 (unique) | CASCADE |

### N:1 (Many-to-One)

| Ребёнок | Родитель | Колонка |
|---------|----------|---------|
| client_profiles | users | user_id |
| master_profiles | users | user_id |
| services | master_profiles | master_id |
| appointments | master_profiles | master_id |
| appointments | services | service_id |
| appointments | client_profiles | client_id |
| working_hours | master_profiles | master_id |
| blocked_slots | master_profiles | master_id |
| reviews | master_profiles | master_id |
| reviews | appointments | appointment_id |
| refresh_tokens | users | user_id |
| audit_logs | users | master_id |
| cities | countries | country_id |
| users | cities | city_id |

### Важные нюансы

1. **Супер-админ (ADMIN) НЕ имеет MasterProfile.** `master_profiles` = NULL для role=ADMIN.
2. **client_id в appointments** — это `client_profiles.id`, а не `users.id`.
3. **master_id в appointments** — это `master_profiles.id`, а не `users.id`.
4. **master_id в audit_logs** — это `users.id` (НЕ master_profiles!).

---

## Миграции Alembic

### Цепочка миграций (squash 1.12.0)

| # | Revision | Down | Описание | Дата |
|---|----------|------|----------|------|
| 1 | 5280b944554f | None | baseline_full_schema — все 13 таблиц из моделей (проверено: upgrade с нуля == `Base.metadata`) | 2026-10-10 |

**Head:** `5280b944554f`

> Старая цепочка из 12 миграций (`9a9c2edb` → `b2c3d4e5f6a7`) удалена после squash —
> история сохранена в git (`git log -- alembic/versions/`). Прод-БД со старым head
> штампуются автоматически (`alembic stamp 5280b944554f` в deploy workflow),
> данные не затрагиваются. Дата-миграция `a1b2c3d4e5f6` (backfill городов)
> новым БД не нужна — города льются сидами (`seed_common.ensure_geography`).

### Применение миграций

```bash
# На сервере:
cd /var/www/beauty-specialist/online-booking/backend
source venv/bin/activate
DATABASE_URL=$(grep DATABASE_URL .env | cut -d= -f2)
alembic upgrade head
```

### Создание новой миграции

```bash
cd /var/www/beauty-specialist/online-booking/backend
source venv/bin/activate
DATABASE_URL=$(grep DATABASE_URL .env | cut -d= -f2)
alembic revision -m "description of changes"
```

---

## Частые ошибки БД и как их избежать

### 1. MissingGreenlet — lazy loading в async SQLAlchemy

**Симптом:**
```
sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called;
can't call await_only() here. Was IO attempted in an unexpected place?
```

**Причина:** При запросе ORM-объекта (например, `MasterProfile`) без предварительной загрузки связанных моделей (`User`), при попытке доступа к `master_profile.user.name` SQLAlchemy пытается выполнить lazy load. В async-сессии lazy load невозможен.

**Решение:**
```python
# Плохо:
result = await db.execute(
    select(MasterProfile)
    .where(MasterProfile.id == master_id)
)

# Хорошо:
result = await db.execute(
    select(MasterProfile)
    .options(selectinload(MasterProfile.user))  # <-- Загружаем user
    .where(MasterProfile.id == master_id)
)
```

**Когда нужно:**
- При чтении `master_profile.user.*` -> добавь `selectinload(MasterProfile.user)`
- При чтении `appointment.client_profile.*` -> добавь `selectinload(Appointment.client_profile)`
- При чтении `appointment.service.*` -> добавь `selectinload(Appointment.service)`
- При чтении `user.master_profile.*` -> добавь `selectinload(User.master_profile)`

### 2. NOT NULL constraint failed: master_profiles.user_id

**Симптом:**
```
sqlite3.IntegrityError: NOT NULL constraint failed: master_profiles.user_id
```

**Причина:** `new_user.id` равен `None` до `flush()`.

**Решение:**
```python
new_user = User(...)
db.add(new_user)
await db.flush()  # <-- Получаем ID

master_profile = MasterProfile(user_id=new_user.id)
db.add(master_profile)
```

### 3. Timezone-aware vs naive datetime comparison

**Симптом:**
```
TypeError: can't compare offset-naive and offset-aware datetimes
```

**Причина:** `RefreshToken.expires_at` — `DateTime(timezone=True)` в PostgreSQL, SQLAlchemy возвращает timezone-aware datetime. Сравнение с naive datetime вызывает TypeError.

**Решение:**
```python
# Плохо:
if expires_at.replace(tzinfo=None) < now:  # TypeError!

# Хорошо:
if expires_at.tzinfo is None:
    expires_at = expires_at.replace(tzinfo=datetime.timezone.utc)
# Теперь оба timezone-aware
```

### 4. Column(Time) требует datetime.time, не строки

**Симптом:**
```
str has no attribute hour
```

**Причина:** `start_time="09:00:00"` — строка. `Column(Time)` требует `datetime.time` объект.

**Решение:**
```python
from datetime import time

# Плохо:
WorkingHour(start_time="09:00:00", end_time="18:00:00")

# Хорошо:
WorkingHour(start_time=time(9, 0), end_time=time(18, 0))
```

### 5. GRANT ALL PRIVILEGES != смена владельца таблицы

**Симптом:** `ALTER TABLE` падает с "permission denied"

**Причина:** `GRANT ALL PRIVILEGES TO specialist` не меняет владельца таблицы. Если таблица создана `postgres`, а миграции запускает `specialist`, `ALTER TABLE` падает.

**Решение:**
```sql
-- Плохо:
GRANT ALL PRIVILEGES ON TABLE audit_logs TO specialist;

-- Хорошо:
ALTER TABLE audit_logs OWNER TO specialist;
```

### 6. ALTER TABLE ADD COLUMN падает если колонка уже есть

**Симптом:** `duplicate column`

**Решение:**
```sql
-- Плохо:
ALTER TABLE cities ADD COLUMN name VARCHAR(100);

-- Хорошо:
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='cities' AND column_name='name'
    ) THEN
        ALTER TABLE cities ADD COLUMN name VARCHAR(100);
    END IF;
END $$;
```

### 7. UNIQUE constraint failed: users.email / users.phone

**Симптом:**
```
sqlite3.IntegrityError: UNIQUE constraint failed: users.email
```

**Причина:** Дублирование email или телефона.

**Решение:** Проверять уникальность перед INSERT и возвращать 409 Conflict.

### 8. При удалении связанных объектов — удаляй их правильно

**Симптом:** `IntegrityError: NOT NULL constraint failed: client_profiles.user_id`

**Причина:** Удаляем User, но ClientProfile остаётся с user_id=NULL.

**Решение:**
```python
# Сначала удаляем зависимые записи
profile = await db.execute(
    select(ClientProfile).where(ClientProfile.user_id == user_id)
)
if profile:
    await db.delete(profile.scalar())

# Потом удаляем пользователя
await db.delete(user)
await db.commit()
```

### 9. appointment.client_id — это user.id, а не client_profile.id

**Симптом:** Ничего не найдено при запросе ClientProfile

**Решение:**
```python
# Плохо:
select(ClientProfile).where(ClientProfile.id == appointment.client_id)

# Хорошо:
select(ClientProfile).where(ClientProfile.user_id == appointment.client_id)
```

---

## Ручные запросы

### Проверка подключения
```sql
-- Проверить подключение
SELECT 1;

-- Проверить версию PostgreSQL
SELECT version();

-- Посчитать пользователей по ролям
SELECT role, count(*) FROM users GROUP BY role;

-- Посчитать записи по статусам
SELECT status, count(*) FROM appointments GROUP BY status;

-- Посчитать мастеров по статусам
SELECT status, count(*) FROM master_profiles GROUP BY status;
```

### Бэкап и восстановление

```bash
# Бэкап
pg_dump -U postgres online_booking > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление
psql -U postgres online_booking < backup_20261007_100000.sql

# Бэкап с сжатием
pg_dump -U postgres online_booking | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Восстановление из сжатого
gunzip -c backup_20261007_100000.sql.gz | psql -U postgres online_booking
```

### Мониторинг

```sql
-- Размер БД
SELECT pg_size_pretty(pg_database_size('online_booking'));

-- Активные соединения
SELECT count(*) FROM pg_stat_activity WHERE datname = 'online_booking';

-- Топ-10 запросов по времени
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Заблокированные запросы
SELECT blocked_pid, blocked_query, blocking_pid, blocking_query
FROM pg_stat_activity blocked
JOIN pg_stat_activity blocking ON blocked.blocking_pid = blocking.pid
WHERE blocked.blocking_pid IS NOT NULL;
```

---

## Checklist перед изменением БД

- [ ] `alembic revision -m "description"` — создал миграцию
- [ ] `alembic upgrade head` — применил на локальной БД
- [ ] Протестировал миграции на SQLite (aiosqlite)
- [ ] Протестировал миграции на PostgreSQL (локально или staging)
- [ ] Проверил `alembic downgrade` (если нужно)
- [ ] Нет `GRANT ALL PRIVILEGES` вместо `ALTER TABLE ... OWNER TO`
- [ ] Нет `Column(Time)` со строковыми значениями
- [ ] Нет сравнения timezone-aware и naive datetime
- [ ] Нет lazy loading в async контексте (все `selectinload`/`joinedload`)
- [ ] Нет `flush()` перед созданием связанных объектов
- [ ] Нет `master.master_profile.id` для супер-админа
- [ ] Проверил `grep -r "old_relationship_name" app/` — все использованы

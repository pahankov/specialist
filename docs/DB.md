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
| last_name | VARCHAR(100) | NULLABLE | Фамилия (отображается вместе с именем: «Имя Фамилия») |
| role | ENUM | NOT NULL, DEFAULT CLIENT | CLIENT, MASTER, ADMIN |
| city_id | INTEGER | FK -> cities.id, NULLABLE | Город пользователя |
| is_active | BOOLEAN | DEFAULT TRUE | Мягкое удаление |
| is_verified | BOOLEAN | DEFAULT FALSE | Верификация (email/phone) |
| max_user_id | BIGINT | UNIQUE, NULLABLE | Привязанный MAX-аккаунт (push-вход без share; ставится при первом MAX-входе) |
| max_username | VARCHAR(64) | NULLABLE | MAX-никнейм (@username) с привязки; может отсутствовать |
| vk_user_id | BIGINT | UNIQUE, NULLABLE | Привязанный VK ID-аккаунт (первый VK-вход; дальше вход по нему без телефона/email) |
| yandex_user_id | BIGINT | UNIQUE, NULLABLE | Привязанный Yandex ID-аккаунт (первый Яндекс-вход) |
| avatar_url | VARCHAR(500) | NULLABLE | Фото из соцсети (CDN провайдера) — клиентское; у мастеров своё `master_profiles.avatar_url` |
| name_source | VARCHAR(16) | NULLABLE | Откуда отображаемое имя: NULL (до трекинга) / `user` (правил человек) / `vk` / `yandex` / `max` |
| created_by | INTEGER | FK -> users.id ON DELETE SET NULL, NULLABLE | Кто создал (мастер через «+ Добавить клиента»/запись); свои клиенты мастера = с записями у него ИЛИ created_by = он |
| consent_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Момент согласия (галочка при регистрации; NULL = до трекинга) |
| consent_policy_version | VARCHAR(20) | NULLABLE | Версия политики ПДн на момент согласия |
| consent_offer_version | VARCHAR(20) | NULLABLE | Версия оферты на момент согласия |
| deleted_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Момент самоудаления (NULL = активен; ПДн обезличены, строки хранятся 3 года) |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

**Индексы:** `ix_users_email` (UNIQUE), `ix_users_phone` (UNIQUE), `ix_users_role`, `ix_users_max_user_id` (UNIQUE, NULL не конфликтуют), `ix_users_vk_user_id` (UNIQUE, NULL не конфликтуют), `ix_users_yandex_user_id` (UNIQUE, NULL не конфликтуют), `ix_users_created_by`

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
| address | VARCHAR(500) | NULLABLE | Локация клиента (подсказки DaData; ключ подбора — users.city_id) |
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
| avatar_url | VARCHAR(500) | NULLABLE | URL аватара (путь `/static/...` на бэкенде; взаимоисключающе с пресетом) |
| avatar_preset | VARCHAR(12) | NULLABLE | Стандартный аватар-эмодзи, 16 штук (🐱🐶🐥🦅🦊🐼🐸🦁🐯🐰🐷🐮🐵🐔🦄🐙) |
| telegram_username | VARCHAR(100) | NULLABLE | Telegram username |
| experience_years | INTEGER | NULLABLE | Опыт работы (лет) |
| status | VARCHAR(20) | NOT NULL, DEFAULT active | active, inactive, suspended |
| is_active | BOOLEAN | DEFAULT TRUE | Мягкое удаление |
| auto_confirm | BOOLEAN | NOT NULL, DEFAULT FALSE | Клиентские записи (кабинет, публичная форма) сразу `confirmed` вместо `pending` |
| auto_complete | BOOLEAN | NULLABLE, DEFAULT FALSE | Прошедшие confirmed-записи сами переходят в `completed` (фоновый цикл) |
| tariff | VARCHAR(20) | NOT NULL, DEFAULT trial | Тариф (фундамент биллинга, пока всем trial) |
| trial_ends_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Конец триала (новым: +180 дней) |
| work_start_hour | INTEGER | NOT NULL, DEFAULT 8 | Начало дневного окна (границы гранул расписания) |
| work_end_hour | INTEGER | NOT NULL, DEFAULT 22 | Конец дневного окна (границы гранул расписания) |
| cabinet_address | VARCHAR(500) | NULLABLE | Адрес кабинета (выбирается через DaData-подсказки; для активации нужен номер дома) |
| certificates | JSON | NOT NULL, DEFAULT [] | Сертификаты [{name, url?}] |
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
| service_id | INTEGER | NULLABLE, FK -> services.id ON DELETE CASCADE | ID услуги (NULL у записей на комплекс) |
| client_id | INTEGER | NOT NULL, FK -> client_profiles.id ON DELETE CASCADE | ID клиента |
| bundle_id | INTEGER | NULLABLE, FK -> service_bundles.id ON DELETE SET NULL | ID комплекса (только у записей на комплекс) |
| bundle_name | VARCHAR(200) | NULLABLE | Снапшот названия комплекса |
| duration_minutes | INTEGER | NULLABLE | Снапшот длительности (комплексы; у услуг — живой join) |
| price | NUMERIC(10,2) | NULLABLE | Снапшот цены (комплексы; у услуг — живой join) |
| discount_label | VARCHAR(200) | NULLABLE | Слепок скидки на момент записи («−20%», «−500 ₽», «купон ABCD −200 ₽») |
| appointment_date | TIMESTAMP WITH TIME ZONE | NOT NULL | Дата и время записи |
| status | VARCHAR(20) | DEFAULT pending | pending, confirmed, completed, cancelled, no_show |
| notes | TEXT | NULLABLE | Примечания |
| created_by_role | VARCHAR(16) | NULLABLE | client / master / admin / public / system; бонусы только у client |
| created_by_user_id | INTEGER | NULLABLE | Пользователь, создавший запись |
| visit_confirmation_status | VARCHAR(16) | NULLABLE | pending / confirmed / disputed (ответ на напоминание) |
| visit_prompt_sent_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Когда отправлено напоминание через 48 ч |
| visit_confirmation_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Когда клиент ответил |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

**Индексы:** `ix_appointments_master_status`, `ix_appointments_master_date`, `ix_appointments_created_by_role`, `ix_appointments_visit_confirmation_status`

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
| discount_percent | INTEGER | NULLABLE, DEFAULT 0 | Скидка 0–90% (0 = нет); клиенты платят effective_price |
| discount_fixed | NUMERIC(10,2) | NULLABLE, DEFAULT 0 | Фикс. −₽ после процента (не ниже нуля) |
| discount_until | TIMESTAMP WITH TIME ZONE | NULLABLE | Срок скидки: после него скидка молча перестаёт действовать |
| category | VARCHAR(50) | NULLABLE | Категория для группировки (Ногти, Шугаринг, ...) |
| is_active | BOOLEAN | DEFAULT TRUE | Активна ли |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

**Индексы:** `ix_services_master_active` (master_id, is_active), `ix_services_category`

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

**Назначение:** OTP коды для SMS-авторизации + MAX-чат-бот вход (channel)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| phone | VARCHAR(20) | NOT NULL | Телефон |
| code_hash | VARCHAR(255) | NOT NULL | Хэш кода |
| expires_at | TIMESTAMP WITH TIME ZONE | NOT NULL | Срок действия |
| is_used | BOOLEAN | DEFAULT FALSE | Сессия по коду выдана (для MAX — только через /max/status) |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| channel | VARCHAR(10) | NOT NULL, DEFAULT 'sms' | 'sms' — код вводится на сайте; 'max' — код шлётся боту |
| max_user_id | BIGINT | NULLABLE | MAX sender, подтвердивший код (факт подтверждения) |
| max_user_name | VARCHAR(200) | NULLABLE | Имя из MAX (дефолт имени нового клиента) |
| max_username | VARCHAR(64) | NULLABLE | Никнейм (@username) из диалога MAX (переносится в `users.max_username`) |
| max_user_email | VARCHAR(255) | NULLABLE | Email из vCard контакта MAX (заполняет пустой email клиента) |
| max_verified_phone | BOOLEAN | NOT NULL, DEFAULT FALSE | TRUE, если номер пришёл через `request_contact` с верным HMAC (доказанно привязан к MAX-аккаунту → `is_verified=True`) |

**Важно:** коды хранятся только в виде хэша (`code_hash`). Легаси-колонка `code` с открытым текстом, оставшаяся на проде со времён до squash, удаляется миграцией `23a1b2c3d4e8` (см. «Частые ошибки» №10).

### 14. service_bundles

**Назначение:** Комплексы услуг мастера (наборы из созданных услуг; в список услуг не смешиваются)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | ID мастера |
| name | VARCHAR(200) | NOT NULL | Название комплекса |
| service_ids | JSON | NOT NULL | Упорядоченные ID услуг (свои, ≥2) |
| durations | JSON | NULLABLE | Переопределения минут {service_id: мин} (нет ключа = своё время услуги) |
| price | NUMERIC(10,2) | NULLABLE | Своя цена; NULL = сумма услуг на момент записи |
| discount_percent | INTEGER | NULLABLE, DEFAULT 0 | Скидка 0–90% на итог комплекса (свою цену или сумму состава) |
| discount_fixed | NUMERIC(10,2) | NULLABLE, DEFAULT 0 | Фикс. −₽ после процента (не ниже нуля) |
| discount_until | TIMESTAMP WITH TIME ZONE | NULLABLE | Срок скидки |
| duration_override | INTEGER | NULLABLE | Ручное общее время комплекса; NULL = сумма минут состава |
| is_active | BOOLEAN | DEFAULT TRUE | Видимость клиентам |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| updated_at | TIMESTAMP WITH TIME ZONE | | Дата обновления |

### 15. notifications

**Назначение:** внутренний «колокольчик» — по строке на получателя (событийные уведомления и рассылки; мессенджер не нужен)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| sender_id | INTEGER | FK -> users.id ON DELETE SET NULL, NULLABLE | Отправитель (NULL — системное) |
| recipient_id | INTEGER | NOT NULL, FK -> users.id ON DELETE CASCADE | Получатель |
| text | TEXT | NOT NULL | Текст уведомления |
| audience | VARCHAR(20) | NULLABLE | Аудитория рассылки: all / masters / clients / my_clients / selected; у событийных — NULL |
| link | VARCHAR(50) | NULLABLE | Диплинк-ключ (например `appointments`) — раздел разворачивает сам |
| kind | VARCHAR(32) | NULLABLE | Тип события (`visit_feedback`, `billing_*`); NULL у старых строк |
| appointment_id | INTEGER | NULLABLE, FK -> appointments.id ON DELETE SET NULL | Запись для действий из уведомления |
| resolved_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Когда действие по уведомлению выполнено |
| is_read | BOOLEAN | NOT NULL, DEFAULT FALSE | Прочитано ли |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |
| read_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Когда прочитано |

**Индексы:** `ix_notifications_recipient_id`, `ix_notifications_recipient_created` (recipient_id, created_at), `ix_notifications_recipient_unread` (recipient_id, is_read), `ix_notifications_kind`, `ix_notifications_appointment_id`

### 16. notification_broadcasts

**Назначение:** история отправленных рассылок («что/когда/кому я отправлял»); получатели — снапшот `[{id, name}]`

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| sender_id | INTEGER | FK -> users.id ON DELETE SET NULL, NULLABLE | Отправитель |
| audience | VARCHAR(20) | NOT NULL | Аудитория |
| text | TEXT | NOT NULL | Текст |
| recipients | JSON | NOT NULL, DEFAULT [] | Снапшот получателей `[{id, name}]` (имена читаемы после переименований) |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата отправки |

**Индексы:** `ix_broadcasts_sender_created` (sender_id, created_at)

### 17. master_hidden_clients

**Назначение:** архив/чёрный список — мастер убрал клиента из своих списков; прошлая история у мастера рендерится обезличенно («Удалённый клиент»)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_profile_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | Мастер |
| client_profile_id | INTEGER | NOT NULL, FK -> client_profiles.id ON DELETE CASCADE | Клиент |
| hidden_at | TIMESTAMP WITH TIME ZONE | | Когда скрыт |
| hidden_reason | VARCHAR(30) | NULLABLE | Причина архива: moved / left / inactive / deceased / other (NULL — легаси) |
| block_reason | VARCHAR(30) | NULLABLE | Причина блока: no_show / rude / spam / debt / other (NULL = только архив) |
| block_note | VARCHAR(500) | NULLABLE | Заметка к блоку/архиву |
| is_blocked | BOOLEAN | NOT NULL, DEFAULT FALSE | Чёрный список: скрыт + запрет новой записи |
| blocked_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Когда заблокирован |

**Индексы:** UNIQUE `(master_profile_id, client_profile_id)`, `ix_hidden_by_master` (master_profile_id)

### 18. coupons

**Назначение:** персональные купоны мастера своим клиентам (−% или −₽); применяются в кабинете, скидка слепком падает на запись

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| master_id | INTEGER | NOT NULL, FK -> master_profiles.id ON DELETE CASCADE | Мастер |
| code | VARCHAR(24) | NOT NULL | Код (латиница/цифры); уникален в рамках мастера — проверяется в коде (409) |
| kind | VARCHAR(10) | NOT NULL, DEFAULT 'percent' | `percent` (1–90) или `fixed` (₽, не выше цены) |
| value | NUMERIC(10,2) | NOT NULL, DEFAULT 0 | Номинал скидки |
| max_uses | INTEGER | NULLABLE | Лимит использований (NULL = без лимита) |
| used_count | INTEGER | NOT NULL, DEFAULT 0 | Использовано раз |
| user_ids | JSON | NULLABLE | Аудитория: NULL = все свои клиенты, иначе список user id |
| valid_until | TIMESTAMP WITH TIME ZONE | NULLABLE | Срок действия |
| is_active | BOOLEAN | NOT NULL, DEFAULT TRUE | Включён ли |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата создания |

**Индексы:** `ix_coupons_master_id`

### 19. coupon_uses

**Назначение:** факты применения купонов (история; выключение купона её не трогает)

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| coupon_id | INTEGER | NOT NULL, FK -> coupons.id ON DELETE CASCADE | Купон |
| appointment_id | INTEGER | NULLABLE, FK -> appointments.id ON DELETE SET NULL | Запись (история переживает удаление записи) |
| user_id | INTEGER | NULLABLE, FK -> users.id ON DELETE SET NULL | Кто применил |
| amount | NUMERIC(10,2) | NOT NULL, DEFAULT 0 | Фактический размер скидки |
| created_at | TIMESTAMP WITH TIME ZONE | | Дата применения |

**Индексы:** `ix_coupon_uses_coupon_id`

### 20. user_contacts

**Назначение:** контакты аккаунта (телефоны/почты) с собственными флагами верификации — основа «Единого входа» 1.79.0; `users.phone/email` остаются легаси-зеркалом на время перехода

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| user_id | INTEGER | NOT NULL, FK -> users.id ON DELETE CASCADE | Владелец контакта |
| contact_type | VARCHAR(10) | NOT NULL | `phone` или `email` |
| value | VARCHAR(255) | NOT NULL | Телефон в формате `+7 (XXX) XXX-XX-XX`; почта в нижнем регистре |
| is_verified | BOOLEAN | NOT NULL, DEFAULT FALSE | Подтверждён ли контакт |
| verified_via | VARCHAR(16) | NULLABLE | Чем подтверждён: `social` (соцвход) или `code` (код на почту) |
| verified_at | TIMESTAMP WITH TIME ZONE | NULLABLE | Когда подтверждён |
| is_primary | BOOLEAN | NOT NULL, DEFAULT FALSE | Основной в своём типе (телефон приоритетнее почты) |
| created_at / updated_at | TIMESTAMP WITH TIME ZONE | | |

**Индексы:** `ix_user_contacts_user_id`; уникальный `ix_user_contacts_type_value (contact_type, value)` — значение живёт ровно на одном аккаунте; перенос «занятого» подтверждённого контакта пишется в аудит

### 21. email_codes

**Назначение:** одноразовые шестизначные коды на почту («Забыли пароль», подтверждение почты); в БД хранится только хэш

| Колонка | Тип | Ограничения | Описание |
|---------|-----|-------------|----------|
| id | INTEGER | PK | Автоинкремент |
| email | VARCHAR(255) | NOT NULL | Адрес получателя (нижний регистр) |
| purpose | VARCHAR(20) | NOT NULL | Назначение (например, `password_reset`) |
| code_hash | VARCHAR(64) | NOT NULL | SHA-256 код (открытый текст не хранится) |
| expires_at | TIMESTAMP WITH TIME ZONE | NOT NULL | Срок жизни кода |
| is_used | BOOLEAN | NOT NULL, DEFAULT FALSE | Одноразовость |
| attempts | INTEGER | NOT NULL, DEFAULT 0 | Неверные попытки (после лимита код сгорает) |
| created_at | TIMESTAMP WITH TIME ZONE | | |

**Индексы:** `ix_email_codes_email`, `ix_email_codes_email_purpose`

### 22. billing (1.84.0)

**Назначение:** ручная оплата и ledger мастеров. Деньги — `NUMERIC(10,2)`, ссылка на источник хранится в `source_ref`, повторные начисления защищены статусами.

| Таблица | Назначение |
|---------|------------|
| `master_billing_accounts` | Trial-даты, статус доступа (`trial/active/readonly/paused/suspended`), реферальный код, флаги качества. 1:1 к `master_profiles` |
| `billing_invoices` | Счета лестницы: 1–2-й месяц — 250 ₽, с 3-го — 500 ₽; issue/due/block, частичная оплата, кредиты |
| `billing_payments` | Подтверждённые администратором платежи (method, note, кто подтвердил, когда) |
| `billing_credits` | Бонусы и ручные начисления с остатком и сроком 90 дней |
| `billing_credit_applications` | Какая сумма каждого кредита ушла в какой счёт (один row на пару credit/invoice) |
| `client_bonus_awards` | Одноразовый бонус первого месяца: кандидаты, 30%-флаг качества, статус и снапшот |
| `master_referrals` | Приглашение A→B, прогресс B, статус и сумма 125 ₽ |
| `referral_clicks` | Одноразовые токены публичных ссылок `/r/:code`, срок 60 дней |

**Индексы:** `ix_billing_accounts_status`, `ix_billing_invoices_master_status` (master_id, status), `ix_billing_credits_master_remaining` (master_id, remaining), `ix_master_referrals_referrer_status` (referrer_master_id, status); уникальные `master_billing_accounts.master_id`, `master_billing_accounts.referral_code`, `billing_invoices (master_id, period_index)`, `client_bonus_awards.master_id`, `referral_clicks.token`, `master_referrals.referred_user_id` и `master_referrals.referred_master_id`.

---

## Связи (Relationships)

### 1:N (One-to-Many)

| Родитель | Ребёнок | Тип | ON DELETE |
|----------|---------|-----|-----------|
| users | client_profiles | 1:1 (unique) | CASCADE |
| users | master_profiles | 1:1 (unique) | CASCADE |
| master_profiles | services | 1:N | CASCADE |
| master_profiles | service_bundles | 1:N | CASCADE |
| service_bundles | appointments | 1:N | SET NULL |
| master_profiles | working_hours | 1:N | CASCADE |
| master_profiles | blocked_slots | 1:N | CASCADE |
| master_profiles | reviews | 1:N | CASCADE |
| users | refresh_tokens | 1:N | CASCADE |
| cities | users | 1:N | SET NULL |
| countries | cities | 1:N | CASCADE |
| appointments | reviews | 1:1 (unique) | CASCADE |
| users | notifications (sender) | 1:N | SET NULL |
| users | notifications (recipient) | 1:N | CASCADE |
| users | notification_broadcasts (sender) | 1:N | SET NULL |
| master_profiles | master_hidden_clients | 1:N | CASCADE |
| client_profiles | master_hidden_clients | 1:N | CASCADE |
| master_profiles | coupons | 1:N | CASCADE |
| coupons | coupon_uses | 1:N | CASCADE |
| appointments | coupon_uses | 1:N | SET NULL |
| users | coupon_uses | 1:N | SET NULL |
| users | user_contacts | 1:N | CASCADE |

### N:1 (Many-to-One)

| Ребёнок | Родитель | Колонка |
|---------|----------|---------|
| client_profiles | users | user_id |
| master_profiles | users | user_id |
| services | master_profiles | master_id |
| service_bundles | master_profiles | master_id |
| appointments | service_bundles | bundle_id |
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
| notifications | users | sender_id, recipient_id |
| notification_broadcasts | users | sender_id |
| master_hidden_clients | master_profiles | master_profile_id |
| master_hidden_clients | client_profiles | client_profile_id |
| user_contacts | users | user_id |
| coupons | master_profiles | master_id |
| coupon_uses | coupons | coupon_id |
| coupon_uses | appointments | appointment_id |
| coupon_uses | users | user_id |

### Важные нюансы

1. **Супер-админ (ADMIN) НЕ имеет MasterProfile.** `master_profiles` = NULL для role=ADMIN.
2. **client_id в appointments** — это `client_profiles.id`, а не `users.id`.
3. **master_id в appointments** — это `master_profiles.id`, а не `users.id`.
4. **master_id в audit_logs** — это `users.id` (НЕ master_profiles!).
5. **Статус клиентской записи зависит от `master_profiles.auto_confirm`:** включён — сразу `confirmed`, выключен — `pending` (кабинет и публичная форма, см. `client/router.py`, `booking/router.py`).
6. **Купоны:** `code` уникален в рамках мастера (проверка в коде → 409); применение фиксируется в `coupon_uses`, а слепок скидки — в `appointments.discount_label`.
7. **`users.avatar_url` / `name_source` — только клиентские:** мастера используют `master_profiles.avatar_url` (загрузка) или `avatar_preset`; `name_source="user"` защищает имя от перезаписи соц-входом (`services/social_merge.py`).

---

## Миграции Alembic

### Цепочка миграций (squash 1.12.0)

| # | Revision | Down | Описание | Дата |
|---|----------|------|----------|------|
| 1 | 5280b944554f | None | baseline_full_schema — все 13 таблиц из моделей (проверено: upgrade с нуля == `Base.metadata`) | 2026-10-10 |
| 2 | c4d5e6f7a8b9 | 5280b944554f | MAX-поля `otp_codes` (channel/max_user_id/max_user_name) | 2026-10-10 |
| 3 | d5e6f7a8b9c1 | c4d5e6f7a8b9 | `otp_codes.max_verified_phone` | 2026-10-10 |
| 4 | e6f7a8b9c1d2 | d5e6f7a8b9c1 | `users.max_user_id` (привязка MAX-аккаунта) | 2026-10-10 |
| 5 | f7a8b9c1d2e3 | e6f7a8b9c1d2 | `services.category` + backfill по ключевым словам | 2026-10-11 |
| 6 | a1b2c3d4e5f6 | f7a8b9c1d2e3 | таблица `notifications` (внутренний колокольчик) | 2026-10-11 |
| 7 | c3d4e5f6a7b8 | a1b2c3d4e5f6 | `users.created_by` (свои клиенты мастера) | 2026-10-11 |
| 8 | d4e5f6a7b8c9 | c3d4e5f6a7b8 | таблица `notification_broadcasts` (история отправок) | 2026-10-11 |
| 9 | e5f6a7b8c9d0 | d4e5f6a7b8c9 | `users.last_name`, `master_profiles.cabinet_address/certificates` | 2026-10-12 |
| 10 | f6a7b8c9d0e1 | e5f6a7b8c9d0 | `client_profiles.address` (локация клиента; ключ подбора — `users.city_id`) | 2026-10-12 |
| 11 | 07b8c9d0e1f2 | f6a7b8c9d0e1 | `notifications.link` (диплинк в записи) | 2026-10-12 |
| 12 | 08c9d0e1f2a3 | 07b8c9d0e1f2 | `master_profiles.avatar_preset` (стандартный аватар-эмодзи) | 2026-10-12 |
| 13 | 09e0f1a2b3c4 | 08c9d0e1f2a3 | `service_bundles` + `appointments.bundle_id/bundle_name/duration_minutes/price`, `service_id` NULLABLE | 2026-10-12 |
| 14 | 0af0e1d2c3b4 | 09e0f1a2b3c4 | `service_bundles.durations` (своё время услуги в комплексе) | 2026-10-12 |
| 15 | 0cf0a1b2c3d4 | 0af0e1d2c3b4 | `users.consent_at/consent_policy_version/consent_offer_version` (доказательство согласия) | 2026-10-12 |
| 16 | 0d0e1f2a3b4c | 0cf0a1b2c3d4 | `users.deleted_at` (метка самоудаления, retention 3 года) | 2026-10-13 |
| 17 | 0e0f1a2b3c4d | 0d0e1f2a3b4c | `master_hidden_clients` (клиент убран из списков мастера, история цела) | 2026-10-13 |
| 18 | 0f101a2b3c4d | 0e0f1a2b3c4d | `master_hidden_clients.is_blocked/blocked_at` (чёрный список: запрет новой записи) | 2026-10-13 |
| 19 | 0f1a2b3c4d5e | 0f101a2b3c4d | `master_hidden_clients.hidden_reason` (причина архива: moved/left/inactive/deceased/other) | 2026-10-13 |
| 20 | 10a1b2c3d4e5 | 0f1a2b3c4d5e | `master_hidden_clients.block_reason/block_note` (причина блока + текст) | 2026-10-13 |
| 21 | 11a1b2c3d4e5 | 10a1b2c3d4e5 | `master_profiles.auto_confirm` (автоподтверждение заявок) | 2026-10-14 |
| 22 | 12a1b2c3d4e5 | 11a1b2c3d4e5 | `service_bundles.duration_override` (ручное время комплекса) | 2026-10-14 |
| 23 | 13a1b2c3d4e5 | 12a1b2c3d4e5 | `master_profiles.auto_complete` (автозавершение прошедших записей) | 2026-10-14 |
| 24 | 14a1b2c3d4e5 | 13a1b2c3d4e5 | `services.discount_percent`, `service_bundles.discount_percent` (скидка 0–90%) | 2026-10-15 |
| 25 | 15a1b2c3d4e5 | 14a1b2c3d4e5 | `services.discount_until`, `service_bundles.discount_until` (срок скидки) | 2026-10-15 |
| 26 | 16a1b2c3d4e5 | 15a1b2c3d4e5 | `coupons`, `coupon_uses` (персональные коды −%/−₽ своим клиентам) | 2026-10-15 |
| 27 | 17a1b2c3d4e5 | 16a1b2c3d4e5 | `services.discount_fixed`, `service_bundles.discount_fixed` (−₽ после %) | 2026-10-15 |
| 28 | 18a1b2c3d4e5 | 17a1b2c3d4e5 | `appointments.discount_label` (слепок скидки на записи) | 2026-10-15 |
| 29 | 19a1b2c3d4e5 | 18a1b2c3d4e5 | `users.max_username`, `otp_codes.max_username/max_user_email` (MAX-профиль из диалога) | 2026-10-17 |
| 30 | 20a1b2c3d4e5 | 19a1b2c3d4e5 | `users.vk_user_id` (unique, привязка VK ID) | 2026-10-17 |
| 31 | 21a1b2c3d4e6 | 20a1b2c3d4e5 | `users.yandex_user_id` (unique, привязка Yandex ID) | 2026-10-17 |
| 32 | 22a1b2c3d4e7 | 21a1b2c3d4e6 | `users.avatar_url/name_source` (соц-профиль клиента) | 2026-10-18 |
| 33 | 23a1b2c3d4e8 | 22a1b2c3d4e7 | DROP `otp_codes.code` — легаси-колонка с открытым текстом, ломавшая INSERT на проде | 2026-10-18 |
| 34 | 24a1b2c3d4e9 | 23a1b2c3d4e8 | `user_contacts` (несколько телефонов/почт, флаги верификации; бэкфилл из `users.email/phone`, 1.79.0) | 2026-10-19 |
| 35 | 25a1b2c3d4ea | 24a1b2c3d4e9 | `email_codes` (одноразовые коды на почту: сброс пароля и подтверждение, 1.79.0) | 2026-10-19 |
| 36 | 26a1b2c3d4eb | 25a1b2c3d4ea | `master_profiles.prefer_master_panel` (старт сразу в кабинете мастера) | 2026-10-20 |
| 37 | 27b1c2d3e4f5 | 26a1b2c3d4eb | Биллинг 1.84.0: счета, платежи, кредиты, клиентские бонусы, рефералы; провенанс записей; напоминания о визите; перевод существующих мастеров на 14-дневный trial (кроме superuser id=1) | 2026-10-21 |

**Head:** `27b1c2d3e4f5`

> Старая цепочка из 12 миграций (`9a9c2edb` → `b2c3d4e5f6a7`) удалена после squash —
> история сохранена в git (`git log -- alembic/versions/`). Прод-БД со старым head
> переводятся автоматически (deploy workflow: `DELETE FROM alembic_version` +
> `alembic stamp 5280b944554f` — именно в таком порядке, т.к. plain `stamp`
> падает с `Can't locate revision` на отсутствующих старых файлах),
> данные не затрагиваются. Backfill городов новым БД не нужен — города льются сидами (`seed_common.ensure_geography`).

### Применение миграций

> Локальный SQLite (`online_booking.db`): lifespan делает `create_all`,
> который создаёт только **новые таблицы**, но **не добавляет колонки**
> в существующие. После pull'а модели с новой колонкой старый файл
> даст `no such column` на каждый запрос (пример 1.23.0: `users.created_by`).
> Лечится прогоном `alembic upgrade head` с синхронным URL
> (`DATABASE_URL=sqlite:///./online_booking.db`) либо точечным
> `ALTER TABLE` из текста миграции. Все миграции после squash
> идемпотентны и на SQLite (проверка через `inspect`).

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

### 10. Прод-таблица отстала от модели — легаси-колонка ломает INSERT

**Симптом (только на проде, PG):**
```
sqlalchemy.exc.IntegrityError: NotNullViolationError: null value in column "code"
of relation "otp_codes" violates not-null constraint
```
500 на `/auth/max/start` и `/auth/send-otp`; локальный SQLite при этом здоров — таблицу создаёт `create_all` по текущей модели, легаси-колонки там нет.

**Причина:** на проде в `otp_codes` жила колонка `code VARCHAR(10) NOT NULL` (времена открытых кодов, до squash). Модель её не мапит и не заполняет — каждый INSERT падал.

**Решение:** миграция `23a1b2c3d4e8` — `ALTER TABLE otp_codes DROP COLUMN IF EXISTS code` (идемпотентно, безопасна к повторному прогону). Диагностика: `journalctl -u beauty-backend` + `\d otp_codes` в psql. Урок шире: после squash сверяй фактическую схему прода с моделями, а не только `alembic_version`.

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
- [ ] Сверил фактическую схему прода (`\d <таблица>`) с моделями — легаси-колонки ломают INSERT (см. ошибку №10)

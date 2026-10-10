# Online Booking — Система онлайн-записи

Приложение для онлайн-записи клиентов на услуги через веб-интерфейс. Клиент выбирает мастера, услугу и время — мастер управляет записями через админ-панель.

---

## 📚 Документация

| Документ | Описание |
|----------|----------|
| [docs/DEPLOY.md](docs/DEPLOY.md) | Полное руководство по деплою на сервере |
| [docs/DB.md](docs/DB.md) | Документация по базе данных PostgreSQL |
| [LOCAL.md](LOCAL.md) | Локальные секреты и настройки (НЕ для git) |
| [docs/TESTING.md](docs/TESTING.md) | Документация по тестированию backend |
| [docs/DEPLOYMENT_RULES.md](docs/DEPLOYMENT_RULES.md) | Правила и анти-паттерны деплоя |
| [docs/SECRETS.md](docs/SECRETS.md) | Где живут секреты, как достать/добавить (без значений) |
| [docs/API.md](docs/API.md) | Справочник API: таблицы эндпоинтов и curl-кукбук |

---

## 🚀 Деплой: что нового
- **Автоматический деплой:** GitHub Actions workflow полностью автоматизирует развёртывание
  - alembic upgrade head — автоприменение миграций при каждом push в main
  - Создание/обновление суперпользователя pahankov@mail.ru (sync SQLAlchemy, без timezone-ошибок)
  - seed_production.py — заполнение БД тестовыми данными только если пуста
  - Сборка frontend + перезапуск сервисов
- **Timezone fix:** все DateTime колонки в моделях теперь DateTime(timezone=True)
  - 11 моделей, 31 колонка: created_at, updated_at, appointment_date, start_dt, end_dt, expires_at, revoked_at
  - Миграция 43f84fe3057 конвертирует колонки в TIMESTAMP WITH TIME ZONE на PostgreSQL
- **GitHub Secrets:** один секрет DATABASE_URL вместо пяти (DB_USER, DB_PASSWORD, DB_HOST, DB_NAME, DB_PORT)
  - Формат: postgresql+psycopg2://user:pass@host:port/dbname
- **Новые файлы:** seed_production.py — безопасный seed только для пустой БД
- **Исправления:**
  - alembic.ini — URL берётся из переменной окружения DATABASE_URL
  - create_superuser.py — заменён sync SQLAlchemy в deploy workflow (async вызывал timezone-ошибки)
  - Удалены удалённые таблицы/колонки из миграции (locations, social_accounts, telegram_user_id и др.)

## 🚀 Быстрый старт

### Требования

- **Python** 3.11+
- **Node.js** 20+
- **PostgreSQL** 16 (production, через Docker)

### Запуск

**Быстрый запуск (Windows):**

```
scripts\start.bat              # Backend + Frontend
scripts\run_backend.bat        # Только backend
scripts\run_frontend.bat       # Только frontend
```

**Ручной запуск:**

**Backend:**
```powershell
cd online-booking\backend
$env:PYTHONPATH='.'
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend:**
```powershell
cd online-booking\frontend
npm run dev
```

**Docker (production):**
```bash
docker-compose up -d        # Запуск всех сервисов
docker-compose logs -f      # Просмотр логов
docker-compose down         # Остановка
```

### Доступ

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

### Переменные окружения

Скопируйте `.env.example` в `.env` и настройте:

```powershell
copy .env.example .env
```

См. `.env.example` для полного списка переменных.

### Синхронизация prod → local (только чтение)

Добавленное на сайте (мастера, клиенты, расписание) подтягивается в локальную БД скриптом через admin API — бэкенд менять не нужно:
```powershell
cd online-booking\backend
$env:PROD_EMAIL='admin@example.com'   # PROD_PASSWORD спросит скрыто, в командную строку не пиши
python pull_production.py --dry-run   # только посчитать
python pull_production.py --yes       # залить (сначала спросит, бэкап .db сделает сам)
```
Тянет: страны/города, мастеров (+профили), услуги, рабочие часы, клиентов. Не тянет: записи, пароли (всем ставится dev-пароль из `LOCAL_DEV_PASSWORD`), города пользователей. Обратного направления нет осознанно — прод правится только через сайт/API.

**Автоматически при старте:** `scripts\start.bat` на шаге `[4/8]` подтягивает прод в локальную БД (мастера, клиенты, расписание). Креды берутся из `backend/.env` (`PROD_EMAIL`/`PROD_PASSWORD`, не пушатся); без сети просто предупредит и продолжит с локальной БД. Ничего лишнего запускать не надо.

**Вручную:**

## 📦 Структура проекта

```
beauty-specialist/              # корень репозитория
├── docs/                   # вся документация: API, DB, DEPLOY, DEPLOYMENT_RULES, RULES, TESTING
├── scripts/                # запуск (start/run_*) + серверные скрипты деплоя (*.sh)
├── db/                     # SQL-дампы и сиды (не для git)
├── docker-compose.yml      # Docker-конфиг (PostgreSQL + Redis, production)
├── .env.example            # Шаблон переменных окружения
├── .github/workflows/      # CI: тесты + push-деплой на сервер
└── online-booking/
    ├── backend/
    │   ├── app/
    │   │   ├── main.py           # FastAPI приложение (lifespan, router registration)
    │   │   ├── config.py         # Настройки (SQLite/PostgreSQL, JWT, refresh tokens)
    │   │   ├── database.py       # Подключение к БД (aiosqlite / asyncpg)
    │   │   ├── dependencies/     # auth (JWT, require_master/admin), crud (get_or_404)
    │   │   ├── services/         # audit, sms, cache, background_tasks, export
    │   │   ├── models/           # SQLAlchemy ORM (User, MasterProfile, ClientProfile, City, ...)
    │   │   ├── schemas/          # Pydantic schemas (pagination, client, city, ...)
    │   │   └── modules/          # self-contained пакеты: auth, city, user, booking,
    │   │                         # service, schedule, review, admin/*, dadata
    │   ├── alembic/              # миграции PostgreSQL
    │   ├── tests/                # pytest (~321)
    │   └── requirements.txt
    └── frontend/
        ├── src/
        │   ├── api/              # http (axios + refresh), public/auth/admin/superadmin, dadata
        │   ├── components/common/# Modal, PhoneInput, CitySelect, MasterSelect, ResizableTh, Pager, ...
        │   ├── pages/admin/      # AdminLayout (/admin) + SuperAdminLayout (/super) + страницы
        │   ├── pages/public/     # HomePage, BookingPage
        │   ├── styles/           # общие стили (filters.css — сетка фильтров)
        │   ├── tests/            # Vitest (~75)
        │   ├── utils/            # section (/admin|/super), persistentState, formatPhone, apiError, ...
        │   └── App.tsx           # роутинг: / → /booking → /admin/* → /super/*
        └── package.json
```

### Модульная архитектура

Проект использует модульную архитектуру — каждый функциональный блок инкапсулирован в отдельный пакет (`modules/<feature>/`).

**Правила зависимостей:**
```
main.py
  ↓
modules/*
  ↓
services/*, dependencies/*, models/*
  ↓
utils/
```

**Никогда:**
- ❌ `models` не зависит от `modules`
- ❌ `dependencies` не зависит от `modules`
- ❌ `services` не зависит от `modules`

**Преимущества:**
- **Изоляция:** добавление нового модуля не затрагивает другие части кода
- **Масштабируемость:** каждый модуль содержит `router.py` (эндпоинты), `service.py` (бизнес-логика), `dependencies.py` (зависимости)
- **Чистота:** `main.py` — только импорты модулей (7 строк), без бизнес-логики

**Добавление нового модуля:**
```
1. mkdir modules/<feature>/
2. Создать router.py с эндпоинтами
3. Создать __init__.py с экспортом router
4. Добавить одну строку в main.py:
   app.include_router(feature_router, prefix="/api/v1/feature")
```

## 🛠 Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Backend | FastAPI 0.115, SQLAlchemy 2.0 (async), aiosqlite / asyncpg |
| Auth | JWT (PyJWT, HS256), прямой bcrypt (без passlib), refresh token rotation, httpOnly cookies |
| Migrations | Alembic 1.14 |
| Cache | Redis 7 (optional, graceful degradation) |
| Background tasks | RQ (Redis Queue, optional, graceful degradation) |
| Frontend | React 18, TypeScript 5, Vite 6 |
| HTTP | Axios (interceptors, refresh queue) |
| Тесты | pytest, pytest-asyncio, httpx, Vitest, @testing-library/react |
| Линтинг | ESLint + Prettier |
| Production DB | PostgreSQL 16 |
| Production cache | Redis 7 |
| Rate limiting | Встроенный middleware (60 req/min default) |

## 🤖 MCP-серверы

Проект настроен с 15 MCP-серверами для расширения возможностей GigaCode AI-ассистента. Конфигурация в `.gigacode_vsc/gigacode.jsonc`.

| Сервер | Назначение | Статус |
|--------|-----------|--------|
| **GitHub** | Работа с PR, issues, репозиториями | ✅ |
| **PostgreSQL** | Прямые SQL-запросы к БД | ✅ |
| **Filesystem** | Чтение/запись файлов проекта | ✅ |
| **Playwright** | E2E-тестирование браузера | ✅ |
| **Puppeteer** | Скриншоты и автоматизация браузера | ✅ |
| **Chrome DevTools** | Отладка браузера: DOM, консоль, сеть, производительность | ✅ |
| **SQLite** | Запросы к локальной БД (dev) | ✅ |
| **Docker** | Управление контейнерами и compose | ✅ |
| **DevTools Utils** | 23 утилиты: Base64, JWT, UUID, хеши, QR, regex, cron | ✅ |
| **Markdown Editor** | Редактирование и управление Markdown-файлами | ✅ |
| **Memory** | Граф знаний для сохранения контекста между сессиями | ✅ |
| **Context7** | Актуальная документация библиотек и фреймворков | ✅ |
| **Microsoft Learn** | База знаний Microsoft (Azure, .NET, TypeScript, VS Code) | ✅ |
| **Dynamic MCP** | Динамические инструменты: автоустановка зависимостей, sandbox-выполнение | ✅ |
| **Forage** | Самообучение: агент находит, устанавливает и изучает новые инструменты | ✅ |

### Настройка

1. **GitHub:** замените `ghp_ВАШ_ТОКЕН` в `.gigacode_vsc/gigacode.jsonc` на реальный Personal Access Token (права: `repo`, `read:user`)
2. **PostgreSQL:** connection string берётся из `docker-compose.yml` (`postgres:postgres@localhost:5432/online_booking`)
3. **Filesystem:** разрешены директории проекта и `C:\Project`
4. **SQLite:** указывает на `online-booking/backend/online_booking.db`

Перезапустите GigaCode после изменений конфигурации.

## 📋 Что реализовано

### ✅ Backend
- **Unified User:** единая таблица `users` с role enum (`master`, `client`, `admin`)
- **MasterProfile / ClientProfile:** профили привязаны к User через FK
- Регистрация и аутентификация мастера (JWT + refresh token rotation)
- **OTP-аутентификация для клиентов:** SMS-код на телефон (FakeSmsProvider, Twilio, SMS.ru)
- **Многогородность:** Country/City модели, полная поддержка России + СНГ
- httpOnly cookies для refresh token, readable cookies для access token
- CRUD мастеров (создание, чтение, обновление, удаление)
- CRUD услуг (создание, чтение, обновление, soft-delete)
- CRUD записей (создание, подтверждение, завершение, отмена, удаление)
- CRUD клиентов (создание, чтение, обновление, удаление)
- CRUD заблокированных слотов (блокировка времени)
- CRUD рабочего расписания
- Публичная запись с проверкой конфликтов (409 Conflict при пересечении)
- Админская запись с выбором клиента из БД и проверкой конфликтов
- Расчёт доступных дней и слотов
- Управление клиентами (автоматическое создание при записи)
- Журнал действий (audit logs) — фиксация всех операций
- Экспорт записей и клиентов в CSV
- **Пагинация:** мастера, клиенты, услуги, записи, отзывы, аудит (PaginatedResponse с total count)
- **Redis caching:** кэширование дашборд-статистики (TTL 5 мин), graceful degradation
- **Background tasks (RQ):** фоновый экспорт CSV с job status tracking
- **Health check:** `/health` (быстрый), `/admin/health` (DB + cache + RQ), `/admin/health/verbose` (метрики)
- **API Changelog:** `/admin/changelog` — история версий API
- **OpenAPI docs:** улучшенная документация с markdown-описаниями, examples, custom 422 handler
- Валидация пароля: min 8 символов, 1 заглавная, 1 строчная, 1 цифра, 1 спецсимвол, 4 уникальных символа
- Валидация телефона: 10 цифр, автоформатирование в +7 (XXX) XXX-XX-XX
- Alembic миграции для PostgreSQL
- Авто-создание таблиц для SQLite через `create_all` в lifespan
- Swagger UI документация (`/docs`)
- Rate limiting middleware (60 req/min default, 10 req/min для auth)
- No-show tracking: счётчик неяв клиентов, эндпоинт `/admin/appointments/{id}/no-show`
- **Superadmin appointment actions:** подтверждение/отмена/завершение/удаление/no-show для ВСЕХ записей (не только своих)
- Отзывы и рейтинги: CRUD отзывов, средний рейтинг, публичная страница отзывов
- **Admin reviews:** `/admin/reviews` — пагинированный список, approve/unpublish, average rating
- **Master detail:** `/admin/masters/{id}/full` — полная статистика, рейтинг, отзывы, последние записи
- **Bulk operations:** `/admin/masters/bulk/toggle-active`, `/bulk/suspend`, `/bulk/unsuspend`
- **Master import:** `/admin/masters/import` — загрузка из CSV
- **Master audit:** `/admin/audit-logs?master_id=X` — логи по конкретному мастеру
- **Фикс 422 /admin/services:** параметр `active_only` теперь принимает boolean

### ✅ Frontend
- Главная страница (список мастеров и услуг)
- Страница бронирования с проверкой конфликтов
- **LoginModal:** регистрация мастера с dropdown городов + OTP flow для клиентов
- **Адаптивный sidebar:** collapsible (сворачивается по кнопке), hamburger menu на мобильных (<1024px)
- **Breadcrumb navigation:** навигационная цепочка под sidebar
- **Skeleton loaders:** анимированные "скелеты" вместо текста "Загрузка..."
- **Tooltips:** всплывающие подсказки при наведении на кнопки и статусы
- **Keyboard shortcuts:** `Ctrl+K` — поиск, `?` — подсказка клавиш, `Esc` — закрыть модалку
- **Undo toast:** уведомления с кнопкой "Отменить" для delete-операций (5 сек)
- **Empty states:** красивые заглушки с иконками и CTA при отсутствии данных
- **MasterDetailPage:** детальная карточка мастера с вкладками (Обзор, Отзывы, Логи)
- Админ-панель (13 страниц):
  - Дашборд — статистика записей, клиентов, услуг, доход, рейтинг
  - Записи — фильтрация по статусу, пагинация, подтверждение, завершение, отмена, удаление, no-show
  - Услуги — создание, редактирование, soft-delete, пагинация
  - Клиенты — создание, редактирование, удаление, экспорт CSV, пагинация
  - Расписание — Calendar, TimeSlots, BookingModal, MonthlyStats (рефакторинг из монолита)
  - Логи — журнал всех действий с фильтрацией и пагинацией
  - Мастера — управление мастерами (CRUD, bulk toggle/suspend, импорт CSV, детальная карточка) [суперпользователь]
  - Глобальная статистика — общая статистика по всей системе [суперпользователь]
- Cookie-based auth (без localStorage)
- Axios interceptor с refresh-очередью
- Обработка ошибок 422 (валидация)
- Адаптивный дизайн
- Role-based роутинг: мастер и суперпользователь видят разные страницы
- Секция отзывов клиентов на главной странице
- Кнопка "+" для быстрого добавления рабочего дня в календаре
- ESLint + Prettier для форматирования кода

### ✅ Тесты
- **Backend:** ~270 pytest-тестов (auth, masters, services, appointments, clients, reviews, admin CRUD, rate limiting, refresh tokens, password security, no-show, dadata proxy, superuser, log level)
- **Frontend:** 41 Vitest-тест (helpers, hooks, Modal/ConfirmDialog, auth refresh, dadata fallback)
- 100% покрытие всех эндпоинтов
- In-memory SQLite для изоляции тестов
- pytest-asyncio для асинхронных тестов
- @testing-library/react для компонентных тестов

## API Endpoints

> Полный справочник по эндпоинтам — [docs/API.md](docs/API.md).


## 🔐 Разделы интерфейса: /admin и /super

Панель мастера и панель суперадмина — **два отдельных раздела** одного SPA: свои URL, свой layout, своё меню, свои guards. Общие только UI-компоненты (`PhoneInput`, `CitySelect`, `MasterSelect`, `Modal`) и API-клиент.

| | Мастер (`/admin/*`) | Суперадмин (`/super/*`) |
|---|---|---|
| Layout | `AdminLayout` — «🍬 Мастерская» | `SuperAdminLayout` — «🛡️ Суперпанель» (тёмная тема) |
| Меню | Дашборд, Мои записи, Мои услуги, Клиенты, Расписание | Дашборд, Доход, Мастера, Все записи, Все клиенты, Расписание, Логи |
| Данные | Только свои | Все по системе |
| Guard | Суперадмина редиректит в `/super/dashboard` | Не-суперадмина редиректит в `/admin/dashboard` |

Вход — через модалку на главной (`/`), дальше редирект по роли. Префикс текущей секции отдаёт хук `useSectionPrefix()` (`src/utils/section.ts`) — все внутренние ссылки строятся через него, перекрёстных прыжков между разделами нет.

**Суперпользователь** (мастер с `is_admin=true`):
- **Дашборд** — глобальная статистика (все мастера, все записи, все клиенты, общий доход)
- **Доход** — финансовая аналитика, breakdown по мастерам/услугам
- **Мастера** — CRUD, блокировка, bulk-операции, импорт CSV, детальная карточка (статистика, отзывы, аудит, сессии), имперсонация («войти как мастер» → приземление в `/admin`, выход — обратно в `/super/masters`)
- **Все записи / Все клиенты** — пагинация, фильтры, deep-link `?client_id=`
- **Логи** — журнал действий с фильтром по мастеру
- **Экспорт** — CSV с фоновой обработкой (RQ)

**Различие ролей:**
| Функция | Мастер | Суперпользователь |
|---------|--------|-------------------|
| Дашборд | Свои записи, клиенты, услуги | Всё по системе |
| Записи | Только свои | Все записи |
| Услуги | Только свои | — (раздела нет) |
| Мастера | — | CRUD + права + блокировка |
| Доход | — (карточка скрыта) | Полная аналитика |

## 🗄️ База данных

> **Полная документация БД:** [docs/DB.md](docs/DB.md) — все таблицы, связи, миграции, частые ошибки.

**Локальная разработка:** SQLite (aiosqlite) — таблицы создаются автоматически при старте через `create_all`.

**Production:** PostgreSQL 16 (через Docker Compose) + Alembic миграции.

### Миграции

```powershell
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### Сущности

```
User (id, email, phone, hashed_password, name, role[master|client|admin], city_id, is_active, is_verified, created_at, updated_at)
  ├─ 1:1 ──> MasterProfile (user_id, description, avatar_url, telegram_username, experience_years, status[active|inactive|suspended], is_active)
  │           ├─ 1:N ──> Service (id, master_id, name, description, duration_minutes, price, is_active, cascade delete)
  │           │           └─ 1:N ──> Appointment
  │           ├─ 1:N ──> Appointment (id, master_id, service_id, client_id, appointment_date, status, notes, cascade delete)
  │           │           └─ N:1 ──> ClientProfile
  │           │           └─ N:1 ──> Service
  │           ├─ 1:N ──> WorkingHour (id, master_id, schedule_date[Date], start_time, end_time)
  │           ├─ 1:N ──> AuditLog (id, master_id, action, entity_type, entity_id, details, ip_address, created_at)
  │           ├─ 1:N ──> BlockedSlot (id, master_id, start_dt, end_dt, reason, created_at)
  │           └─ 1:N ──> RefreshToken (id, user_id, token, expires_at, is_revoked, cascade delete)
  │
  ├─ 1:1 ──> ClientProfile (user_id, no_show_count, preferred_service_ids)
  │           └─ 1:N ──> Appointment
  │
  └─ 1:N ──> RefreshToken (id, user_id, token, expires_at, is_revoked, created_at)

Country (id, code[ISO], name_ru, name_en, phone_prefix, is_active)
  └─ 1:N ──> City (id, country_id, name_ru, name_en, slug, is_active)

OtpCode (id, phone, code_hash, expires_at, is_used, created_at)
```

### Роли пользователей
- `master` — мастер услуг (может создавать записи, управлять услугами и расписанием)
- `client` — клиент (аутентификация по SMS-коду, без пароля)
- `admin` — суперпользователь (полный доступ ко всей системе)

### Статусы мастеров
- `active` — работает, принимает записи, появляется в публичном каталоге
- `inactive` — не работает (нет активных рабочих дней или сам отключился), не появляется в каталоге
- `suspended` — заблокирован админом (нарушение правил), не может работать

### Статусы записей
- `pending` — ожидает подтверждения
- `confirmed` — подтверждена
- `cancelled` — отменена
- `completed` — завершена

## 🔒 Безопасность

 1. **Пароли:** Bcrypt hashing напрямую (без passlib), валидация: min 8 символов, 1 заглавная, 1 строчная, 1 цифра, 1 спецсимвол (!@#$%^&* и т.д.), 4 уникальных символа
  2. **Аутентификация:** JWT токены (PyJWT, HS256) + refresh token rotation
 3. **SMS OTP:** 6-значный код на телефон (TTL 5 мин), hash-хранение кода, поддержка Twilio/SMS.ru
 4. **Cookies (split-token):** refresh_token — `httponly=True` (7 суток), access_token — `httponly=False`, TTL 30 мин, читается JS для `Authorization: Bearer` (бэк проверяет только header; полный httpOnly — future work)
 5. **Rate limiting:** 60 req/min default, 10 req/min для auth-эндпоинтов
 6. **Валидация:** Pydantic schemas с проверкой типов
 7. **SQL-инъекции:** Защищено SQLAlchemy ORM
 8. **Логирование:** Цветной вывод в консоль (ANSI), SQL-запросы на уровне WARNING, файлы логов с ротацией

## 🧪 Тесты

```powershell
# Backend
cd online-booking\backend
$env:PYTHONPATH='.'
pytest tests/ -v                          # Все тесты (~321)
pytest tests/test_reviews.py -v           # Только reviews
pytest tests/ -v --cov=app                # С покрытием

# Frontend
cd online-booking\frontend
npx vitest run                            # Все тесты (~75)
npx vitest run src/tests/helpers.test.ts  # Только helpers
npx vitest                              # Watch mode
```

**Важно:** Подробная документация по тестированию — [docs/TESTING.md](docs/TESTING.md).
Включает критические правила, известные проблемы и чек-лист перед коммитом.

## Seed и curl-кукбук

> Seed-скрипты и примеры curl — [docs/API.md](docs/API.md).


## 📚 История версий

### [1.13.0] — 2026-10-10
- **Squash миграций:** 12 файлов → один `5280b944554f_baseline_full_schema` (проверено: upgrade с нуля == `Base.metadata`); `env.py` — транзакционный DDL вместо AUTOCOMMIT; deploy штампует старые прод-БД (`stamp` при head `b2c3d4e5f6a7`), данные не трогаются; `docs/DB.md` обновлён
- **Сиды — один канон:** новый `seed_common.py` (география 7 стран/457 городов, ревью с честными join вместо lazy-доступа); `seed_cities`/`seed_test_data`/`fix_production_db`/`create_minimal_reviews`/`seed_production` — тонкие делегаты (-520/+50 строк); `_hash_pw` ×2 → `hash_password`; суперюзер теперь гарантирует `MasterProfile`
- **Локальная БД:** wipe + `alembic upgrade head` + полный сид (20 мастеров, 60 клиентов, 508 записей, 168 отзывов), суперюзер `pahankov@mail.ru` сохранён; `.bak`-мусор удалён
- **Гигиена:** `.gitattributes` (LF — конец `sed 's/\r$//'` на деплое), удалены мёртвые `schemas/client_profile.py`, `schemas/master_profile.py`

### [1.12.0] — 2026-10-09
- **Логгер:** тихие `/health/docs/openapi` (без INFO-шума), `perf_counter`, без IP/UA в логах, `X-Request-ID` и на 500
- **Лэйауты:** общий `BaseLayout` (`/admin` + `/super` — только nav/заголовок/тема различаются, DOM идентичен)
- **Фронт-дубли:** `constants/statusLabels.ts` (статусы/сущности/действия/уровни), `StatusBadge`, `useAdminSort` (Clients+Masters), фильтры записей через `statusLabels`
- **Страницы:** Logs — именованные API-методы (generic-хак из `adminApi` удалён), `Skeleton`/`EmptyState`; Services — `getApiErrorStatus`, тосты вместо инлайн-бокса, `EmptyState` с CTA
- **Тесты:** +3 (`StatusBadge`, `useAdminSort` цикл asc→desc→none); фронт 78/78, бэкенд 322/322

### [1.11.0] — 2026-10-09
- **Секреты в одном месте:** корневой `.env`-дубль удалён; рантайм-канон — только `online-booking/backend/.env` (gitignored), шаблон — `.env.example`; `docs/SECRETS.md` обновлён
- **Безопасность P0:** `SECRET_KEY` fail-closed (пустой/короткий ключ роняет старт), slowapi реально подключён (60/min глобально + 10/min на auth, `/health` exempt), CORS-методы явно, `Review` добавлен в `alembic/env.py`
- **Баги:** OTP — 6 цифр (`randbelow`, HEX не проходил валидацию), `digits == 11` → `len(digits) == 11`, экспорт — aliased join + `_run()` без блокировки loop, двойной `GET /audit-logs` схлопнут в один role-aware handler
- **Бэкенд-чистота:** `python-jose` → `PyJWT`, `passlib` удалён (прямой bcrypt), `normalize_phone` один (`utils/phone.py`), мёртвый `modules/auth/schemas.py` удалён, токены переехали в `utils/tokens.py` (без module→module), кэш на `redis.asyncio` + `SCAN` + `v1:`, RQ берёт хост из `settings.REDIS_URL`
- **Фронт-чистота:** удалены `@radix-ui/react-dialog`, `date-fns`, мёртвый background-экспорт; `dadata.ts` импортирует `./http` (без цикла); UI-типы расписания → `components/schedule/types.ts`; `AdminLoginResponse` — алиас; Tooltip-классы починены; общий `SelectDropdown.css`; куки только через `utils/cookies`
- **Тесты:** `pytest_asyncio.fixture` в conftest, `RATE_LIMIT_DISABLED` по умолчанию в тестах, кэш-тесты переписаны под async; фронт: 75/75 vitest, `tsc` чисто

### [1.10.0] — 2026-10-09
- **Города везде:** `POST /cities/resolve` (DaData→local id), город у клиента (схемы, CRUD, форма, колонка, bulk-назначение), бэкфилл Москва/Питер/Краснодар миграцией
- **Расписание:** окно рабочего времени (`work_start_hour/end_hour` + миграция, `GET/PATCH /work-window`), гранулы из окна, включение часа активирует день, 1 гранула = 1 живая запись, запрет снятия часа с бронью, бронь суперадмина за выбранного мастера
- **Таблицы:** `ResizableTh` + `useColumnWidths` (память ширин), общий `Pager` (в начало/конец), колонка МАСТЕР и сортировка по ней, общий `filters.css`
- **Drill-down:** баннеры дохода ведут в записи/клиентов со скоупом; фильтры переживают переходы (sessionStorage)
- **Аудит и безопасность:** создание/обновление/удаление мастера в логах, входы/выходы (`auth`), блокировка = оба флага + 403 при входе
- **Экспорты через API-клиент** (blob, с тостами): записи (мастер/ids), клиенты (город, ids/фильтр), мастера; чекбоксы выбора в таблицах
- **Индексы горячих путей** миграцией; дубли телефона/email при update → 400 вместо 500 (проверка только изменённых)

### [1.9.0] — 2026-10-08
- **Разделение секций:** суперадмин переехал на `/super/*` (свой layout, меню, guards), мастер остался на `/admin/*`; общий `PhoneInput`, переписанный `CitySelect`, общий `styles/filters.css`, детерминированная пагинация (tiebreak по id)
- **Реорганизация корня:** `docs/` (вся документация), `scripts/` (запуск + серверные скрипты), `db/` (SQL-дампы); удалён leftover `secrets-to-remove.txt`

### [1.8.0] — 2026-10-08
- **Тарифы (фундамент биллинга):** `tariff` + `trial_ends_at` на мастере, всем — trial +180 дней (миграция с ретро-начислением); бейджи в таблице и карточке
- **Правило active исправлено:** active ⟺ ≥1 будущего рабочего дня (прошлое игнорируется, suspended не трогается)
- **Расписание для суперадмина:** refetch при смене мастера, добавление только выбранному мастеру (себе — 400), правка/удаление чужих часов
- **Доход по мастеру:** вся статистика пересчитывается (`/masters/{id}/stats` + даты), а не только выручка
- **MasterSelect:** живой поиск по имени вместо 4 копипастных селектов (Revenue/Schedule/Clients/Appointments)
- **Сортировка + живой поиск:** Masters (серверная, + дебаунс), Clients (серверная + колонка неявок), Appointments уже была
- **Логи:** фильтры уровня/действия + быстрый поиск по странице
- **Адаптив:** таблицы скроллятся вместо схлопывания кнопок (delete снова видно)

### [1.7.0] — 2026-10-08
- **Панель суперадмина — поддержка:** impersonation (вход от имени мастера с баннером и аудитом, fellow-admin запрещены), сброс пароля с отзывом сессий, вкладка активных сессий + отзыв всех
- **Настоящий logout:** `authApi.logout()` отзывает httpOnly refresh (раньше сессия оставалась жива)
- **Честный UX:** убрано фейковое undo при удалении, удаление мастера — через ConfirmDialog, mount-загрузка списка (был вечный скелетон)
- **Единые ошибки:** `getApiErrorMessage()` в 9 страницах (понимает кастомный 422-формат), общие `utils/cookies`
- **Единая политика паролей:** `validate_password_strength()` вместо 4 копий в схемах

### [1.6.0] — 2026-10-08
- **DaData через прокси:** фронт ходит на same-origin `/api/dadata` (секрета в бандле нет), бэк форвардит тело и зеркалит статус
- **Фолбэк городов:** при отказе DaData — локальная БД (`/api/v1/cities/search/`), сид расширен до 457 городов
- **Дебаунс автокомплита:** 400 мс + отсечение протухших ответов (квота DaData больше не сжигается)
- **Скрипты деплоя без хардкода:** `create_superuser.py` / `fix_production_db.py` читают `SUPERUSER_*` из env, без env — keep, в CI-логи — маски
- **Deploy:** `seed_cities.py` в пайплайне (идемпотентно), integrity-чеки под прокси-архитектуру, superuser-шаг не роняет ран
- **Инцидент:** чистка истории затёрла захардкоженный пароль в скриптах → прод-пароль сбрасывался каждый деплой; вылечено env-подходом (подробности — в истории коммитов)

### [1.5.0] — 2026-10-07
- **Безопасность:** все секреты убраны из трекаемых файлов (канон — `backend/.env` + `LOCAL.md`, зеркало — GitHub Secrets); история переписана (`filter-repo`, 12 замен)
- **P1-баги:** 422-хендлер по классу `RequestValidationError`, refresh через bare axios instance (deadlock), DaData-прокси форвардит body, `LOG_LEVEL` из env
- **P2-бэкенд:** удалён мёртвый `modules/auth/dependencies.py` и `soft_delete`, `hash_password/verify_password` → `utils/security.py`, сплиты `admin/appointments → {actions,listing,booking}` и `admin/dashboard → {overview,reports}`, DaData в `Settings`
- **P3-фронт:** единый `Modal` + `ConfirmDialog` (8 точек, `ui/dialog.tsx` удалён — Tailwind в проекте отсутствует), сплит `client.ts → http/public/auth/admin/superadmin`, удалены дубли и мёртвые компоненты
- **P4-доки:** чеклист только в `DEPLOYMENT_RULES.md`, `otp_codes` на месте, `API.md` вынесен из README (1039→~700 строк)
- **Тесты:** ~270 pytest + 41 vitest (было 135 + 44)

### [1.4.0] — 2026-09-24
- **Фикс суперпользователя:** эндпоинты подтверждения/отмены/завершения записей теперь работают для ADMIN
  - `confirm`, `cancel`, `complete`, `delete`, `no-show` — проверяют `master.role == UserRole.ADMIN`
  - Для ADMIN: `get_or_404` (доступ ко всем записям), без требования `MasterProfile`
  - Для regular master: `get_owned_or_404` (только свои записи)
- **Фикс 422 /admin/services:** параметр `active_only` изменён с `Optional[str]` на `Optional[bool]`
  - Фронтенд конвертирует boolean в string перед отправкой
- **Фикс breadcrumbs:** дублирующиеся ключи `/admin/dashboard` исправлены — уникальные key `breadcrumb-{index}`
- **Фикс Breadcrumb.jsx:** переименован из `.js` в `.jsx` для корректного JSX-парсинга Vite
- **Фикс delete_master:** защита от `AttributeError` при отсутствии `MasterProfile` у суперадмина

### [1.3.0] — 2026-09-24
- **Swiper carousel:** главная страница с бесконечной прокруткой (Services → Masters → Reviews)
  - Swiper v9 с `loop: true` (виртуальные слайды без клонов)
  - Автоплей каждые 4 секунды, пауза при наведении на карточки
  - Навигация стрелками, точки-индикаторы, пагинация
  - Адаптивный дизайн, поддержка свайпов на мобильных
- **Комплексная фильтрация:** все страницы админ-панели с фильтрами
  - **Записи:** фильтрация по мастеру, клиенту, услуге, дате (date range)
  - **Клиенты:** поиск по имени/телефону, фильтр по мастеру (клиенты конкретного мастера)
  - **Доход:** breakdown по мастерам/услугам, date range, master filter
  - **Расписание:** фильтр по мастеру (суперпользователь видит всех)
  - **Рабочие часы:** master_id filter для суперпользователя
  - **Экспорт CSV:** все фильтры передаются в экспорт
- **Seed-скрипт с защитой:** `seed_test_data.py` теперь защищает суперпользователя
  - При очистке базы сохраняет всех ADMIN (role=ADMIN)
  - Проверка существования перед созданием (no duplicates)
  - 20 мастеров, 86 услуг, 60 клиентов, 200 рабочих часов, 508 записей, 168 отзывов
  - Логин: `master0@beauty.ru`...`master19@beauty.ru`, пароль: `password123`
- **Фикс MissingGreenlet:** все lazy-load исправлены
  - `dashboard.py`: joinedload для `master_profile.user` и `client_profile.user`
  - `services.py`: извлечение `mp_id` перед query
  - `clients.py`, `appointments.py`: selectinload для вложенных отношений
- **API:** новые эндпоинты для фильтрации
  - `GET /admin/appointments?master_id=X&client_id=X&service_id=X&date_from=X&date_to=X`
  - `GET /admin/clients?search=X&master_id=X`
  - `GET /admin/revenue-breakdown?by_master=true&by_service=true&date_from=X&date_to=X`
  - `GET /admin/working-hours?master_id=X` (суперпользователь)
- **Frontend:** API client обновлён с новыми параметрами фильтров
- **Фикс bcrypt:** downgrade до 4.3.0 для совместимости с passlib 1.7.4

### [1.2.0] — 2026-09-24
- **UX/UI улучшения:**
  - Адаптивный sidebar: collapsible (кнопка сворачивания), hamburger menu на мобильных
  - Breadcrumb navigation: навигационная цепочка под sidebar
  - Skeleton loaders: анимированные "скелеты" вместо текста "Загрузка..."
  - Tooltips: всплывающие подсказки при наведении на кнопки и статусы
  - Keyboard shortcuts: `Ctrl+K` — поиск, `?` — подсказка, `Esc` — закрыть модалку
  - Undo toast: уведомления с кнопкой "Отменить" для delete-операций (5 сек)
  - Empty states: красивые заглушки с иконками и CTA
- **Производительность и архитектура:**
  - **PaginatedResponse:** пагинация со total count для всех списков (клиенты, записи, услуги, отзывы, аудит)
  - **Redis caching:** кэширование дашборд-статистики (TTL 5 мин), graceful degradation
  - **Background tasks (RQ):** фоновый экспорт CSV с job status tracking
  - **Health check:** `/health` (быстрый), `/admin/health` (DB+cache+RQ), `/admin/health/verbose` (метрики)
  - **API Changelog:** `/admin/changelog` — история версий API
  - **OpenAPI docs:** улучшенная документация с markdown, examples, custom 422 handler
- **Управление мастерами:**
  - **MasterDetailPage:** детальная карточка с вкладками (Обзор, Отзывы, Логи)
  - **Admin reviews:** `/admin/reviews` — пагинированный список, approve/unpublish, average rating
  - **Bulk operations:** `/admin/masters/bulk/toggle-active`, `/bulk/suspend`, `/bulk/unsuspend`
  - **Master import:** `/admin/masters/import` — загрузка из CSV
  - **Master audit:** `/admin/audit-logs?master_id=X` — логи по конкретному мастеру
  - **Full master profile:** `/admin/masters/{id}/full` — статистика, рейтинг, отзывы, записи

### [0.15.0] — 2026-09-24
- **Статусы мастеров:** `active`, `inactive`, `suspended`
- **Автоопределение:** мастер становится `inactive`, если нет активных рабочих дней
- **Блокировка админом:** `/admin/masters/{id}/suspend` и `/admin/masters/{id}/unsuspend`
- **Публичный каталог:** показывает только `active` мастеров
- **Рабочие дни:** `WorkingHour.is_active` — можно отключать отдельные дни
- **Миграция:** 08fbbef38349 (master_status, working_hour_is_active)
- **Сервис:** `services/master_status.py` — управление статусами

### [0.14.0] — 2026-09-24
- **Рефакторинг модульности:** `modules/admin/base.py` (god-файл) → `dependencies/`, `middleware/`, `services/`
- **Зависимости:** `dependencies/auth.py` (JWT), `dependencies/crud.py` (get_or_404, soft_delete)
- **Мидлвари:** `middleware/rate_limit.py` (RateLimiter)
- **Сервисы:** `services/audit.py` (audit logging)
- **Чистота:** каждый модуль импортирует только нужные зависимости, никаких god-файлов
- **Toast уведомления:** `components/Toast.tsx` — всплывающие уведомления с дедупликацией, макс 3 тоста, пауза при наведении
- **Единый форматер телефонов:** `utils/formatPhone.ts` — все поля телефона используют одну функцию
- **UTC время:** `utils/__init__.py` — `utcnow()`, `utcnow_naive()`, `ensure_utc()` — единый стандарт времени
- **Фикс lazy-load:** `clients.py` — добавлен `joinedload` для User при загрузке клиентов
- **Фикс телефона:** `slice(0, 11)` → `replace(/^7/, '')` — пользователь вводит 10 цифр, +7 добавляется автоматически
- **Фикс дубликата телефона:** проверка `UNIQUE constraint` → понятная ошибка "Мастер с таким телефоном уже существует"
- **Фикс бэкапа:** `scripts\start.bat` — автоматический бэкап БД перед запуском
- **Фикс структуры:** `backend/` и `frontend/` перемещены в `online-booking/`

### [0.13.0] — 2026-09-22
- **Unified User:** единая таблица `users` вместо раздельных `masters` и `clients`
- **Role-based access:** role enum (`master`, `client`, `admin`) вместо `is_admin` флага
- **MasterProfile / ClientProfile:** профили привязаны к User через FK
- **Многогородность:** `Country` и `City` модели, полная поддержка России + СНГ
- **OTP-аутентификация:** SMS-код на телефон для клиентов (FakeSmsProvider, Twilio, SMS.ru)
- **Новые endpoints:** `/api/v1/auth/send-otp`, `/api/v1/auth/verify-otp`, `/api/v1/countries/`, `/api/v1/cities/`
- **Frontend:** LoginModal с dropdown городов + OTP flow, новые API types
- **Миграции:** 0004-0009 (countries, cities, unified user, data migration, OTP)
- **Seed:** полный список городов России + основные города СНГ
- **Config:** новые settings для SMS (SMS_PROVIDER, TWILIO_*, SMSC_*)
- **Обновлены модули:** admin (appointments, clients, masters, services, working_hours, blocked_slots, export, global_stats, audit), booking, review, user

### [0.12.0] — 2026-09-22
- **Рефакторинг архитектуры:** flat `api/` (22 файла) → модульная `modules/` (7 пакетов)
- **Модули:** `auth/`, `user/`, `booking/`, `service/`, `schedule/`, `review/`, `admin/`
- **Auth module:** разделение на `router.py`, `service.py`, `token.py`, `dependencies.py`, `schemas.py`
- **Зависимости:** `dependencies.py` перенесён в `modules/auth/`, используется всеми модулями
- **Изоляция:** каждый модуль self-contained, `main.py` — только 7 импортов
- **135 тестов:** все проходят, 100% покрытие
- **Документация:** обновлена структура проекта, добавлена секция про модульную архитектуру

### [0.11.0] — 2026-09-21
- **Тесты:** +28 новых тестов (refresh tokens, rate limiting, password security, no-show) — 135 backend + 44 frontend = 179
- **Логирование:** цветной вывод в консоль (ANSI), SQL-запросы на уровне WARNING, suppress uvicorn access logs
- **Audit logs:** superadmin видит ВСЕ логи системы, master видит только свои; master_name вместо ID в таблице
- **Фикс audit log:** log_action теперь вызывается после flush (ID объекта корректно сохраняется)
- **Константы:** frontend/src/constants.ts — PHONE_PLACEHOLDER, PASSWORD_PLACEHOLDER, EMAIL_PLACEHOLDER, TELEGRAM_PLACEHOLDER
- **Фикс PATCH:** admin_services.py и masters.py — model_dump(exclude_unset=True) предотвращает потерю данных при обновлении
- **Фикс auth:** refresh/logout endpoints возвращают Response с cookies (был баг — TokenRefreshResponse вместо Response)
- **Фикс MastersPage:** пустые query params не вызывают 422
- **Фикс логина:** точный лог — "Суперпользователь" vs "Мастер"
- **Фикс bcrypt:** downgrade до 4.3.0 для совместимости с passlib 1.7.4

### [0.10.0] — 2026-09-21
- **Отзывы и рейтинги:** CRUD отзывов (Backend: `reviews.py`, Frontend: `ReviewsSection`, `ReviewCard`)
- **API отзывов:** `GET /api/v1/reviews/`, `GET /average`, `POST`, `PATCH`, `DELETE`
- **No-show tracking:** `PATCH /admin/appointments/{id}/no-show`, поле `no_show_count` в Client
- **Rate limiting:** middleware с настраиваемыми лимитами (60 req/min default, 10 для auth)
- **Health check:** эндпоинт `/health`
- **Пустые слоты:** кнопка "+" в календаре для быстрого добавления рабочего дня
- **Валидация пароля:** 7 проверок (min 8, 1 заглавная, 1 строчная, 1 цифра, 1 спецсимвол, 4 уникальных)
- **ESLint + Prettier:** линтинг и форматирование кода
- **Frontend-тесты:** 44 Vitest-теста (helpers, hooks, Modal, MessageBar, Pagination, FilterBar)
- **Миграции:** `0002_add_reviews`, `0003_add_no_show_count`
- **CI/CD:** GitHub Actions (backend tests + frontend lint + vitest + build)
- **`.env.example`:** шаблон переменных окружения
- **Очистка:** удалены 31 .js-артефакт из frontend/src/

### [0.9.0] — 2026-09-21
- **Админка суперпользователя:** полное разделение ролей (мастер vs is_admin=true)
- **Управление мастерами:** CRUD мастеров из админ-панели (поиск, фильтрация, создание, редактирование, удаление)
- **Блокировка/разблокировка:** toggle-active для мастеров
- **Назначение прав:** toggle-admin для назначения/снятия прав суперпользователя
- **Глобальная статистика:** дашборд со всеми метриками по системе (все мастера, все записи, все клиенты, общий доход)
- **Статистика по мастеру:** детальные метрики для каждого мастера из админки
- **Role-based роутинг:** мастер и суперпользователь видят разные страницы в навигации
- **Зависимости:** `require_super_admin` для эндпоинтов суперпользователя, защита от удаления себя
- **Фикс bcrypt:** downgrade до 4.3.0 для совместимости с passlib 1.7.4
- **Фикс маршрутов:** trailing slash / masters endpoint (prefix в router, "" вместо "/")
- **Фикс фильтров:** query-параметры is_active/is_admin как строки (alias для FastAPI)
- **Фикс логов:** одна вкладка "Логи" для всех ролей
- **Тесты:** 135 backend + 44 frontend = 179 тестов (все проходят)

### [0.8.0] — 2026-09-21
- **Alembic миграции:** поддержка PostgreSQL через Alembic 1.14
- **Refresh token flow:** rotation + httpOnly cookies, endpoint `/api/v1/auth/refresh` и `/api/v1/auth/logout`
- **Conflict check:** публичная запись проверяет пересечение слотов с существующими (409 Conflict)
- **Рефакторинг SchedulePage:** 710 строк → 5 компонентов (Calendar, TimeSlots, BookingModal, MonthlyStats, helpers)
- **Валидация пароля:** min 8 символов, 1 заглавная, 1 цифра
- **Пагинация:** masters, clients, services (limit/offset, 1-200)
- **LoginModal:** обработка 422 ошибок, подсказка требований пароля, телефон 10 цифр
- **Seed-скрипт:** создание суперпользователя (`seed_superuser.py`)
- **Фиксы:** дубликаты функций в helpers/hooks, ошибка `dt_timezone`, `postgresql_where` в индексах
- **Модели:** cascade delete, Date вместо String(10), timezone.utc, unique phone, индексы
- **Тесты:** 98 тестов (все проходят)

### [0.7.0] — 2026-09-21
- **Логирование:** стандартная система с 5 уровнями (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- **Конфигурация:** `backend/app/logging_config.py` — console + rotating file handler
- **Логирование в API:** регистрация, вход, CRUD всех сущностей, публичные записи
- **Формат логов:** `[timestamp] LEVEL logger_name: message`

### [0.6.1] — 2026-09-21
- **Роли:** добавлен флаг `is_admin` в таблицу `masters` — один мастер может быть суперпользователем
- **Суперпользователь:** Павел (pahankov@mail.ru) — мастер с `is_admin=true`, полный доступ ко всей системе
- **Удалён superadmin:** убрана отдельная таблица `admins`, всё через `masters.is_admin`
- **Форма регистрации:** публичная форма "Стать мастером" на главной странице

### [0.6.0] — 2026-09-20
- **Рефакторинг фронтенда:** страницы разделены на `public/` и `admin/`, добавлены общие компоненты
- **Единый API-клиент:** Axios-интерфейс с auth-interceptor и глобальной обработкой 401
- **Рефакторинг бэкенда:** `admin.py` (901 строк) разбит на 9 модулей (dashboard, appointments, services, clients, working_hours, audit, export, blocked_slots)
- **Админ-эндпоинты:** все под префиксом `/api/v1/admin/*`
- **Полное логирование:** все CRUD-операции записываются в AuditLog (создание, обновление, удаление)
- **Pydantic v2:** миграция `class Config:` → `ConfigDict`
- **Тесты:** расширение с 18 до 97 тестов (100% покрытие)
- **Фиксы:** `ServiceCreate.master_id` required, conflict-check в `book_appointment`, null-bytes в TSX

### [0.5.0] — 2026-09-17
- **Клиенты:** полный CRUD в админ-панели (создание, редактирование, удаление, валидация дублей)
- **Журнал действий:** AuditLog — фиксация всех операций с фильтрацией и пагинацией
- **Заблокированные слоты:** блокировка времени, когда записи невозможны
- **Экспорт CSV:** записей и клиентов из админ-панели
- **Завершение записей:** новый статус `completed`
- **Админская запись:** создание записи из админ-панели с выбором клиента и проверкой конфликтов
- **Пагинация:** список записей (limit/offset)
- **Soft-delete услуг:** услуги скрываются вместо удаления
- **Frontend:** ClientsPage, LogsPage, обновление AppointmentsPage и ServicesPage

### [0.4.0] — 2026-09-15
- **Админ-панель:** JWT-аутентификация, дашборд, управление записями/услугами/расписанием
- **Frontend:** LoginPage, AdminLayout, DashboardPage, AppointmentsPage, ServicesPage, SchedulePage

### [0.3.0] — 2026-09-15
- **Тесты:** 18 pytest-тестов (auth + masters CRUD)
- **Backend:** PATCH/DELETE для мастеров, Schema fixes

### [0.2.0] — 2026-09-09
- JWT-аутентификация, публичная запись, расчёт доступных слотов, статусы записей

### [0.1.0] — 2026-09-09
- Инициальная версия: backend + frontend, 5 моделей, 6 роутеров, Docker Compose

## 🚀 Roadmap

### Phase 2 — Интеграция с мессенджерами
- Telegram Bot — уведомления о записях
- VK Mini App — запись через VK
- Система уведомлений (email/push)

### Phase 3 — Production Ready
- ✅ Alembic миграции (реализовано)
- ✅ CI/CD (GitHub Actions)
- ✅ Frontend-тесты (Vitest)
- Деплой (Nginx, HTTPS)

### В планах
- Множественные мастера с разными графиками
- ✅ Отзывы и рейтинги (реализовано)
- Уведомления (Telegram/email)
- Платёжная система (ЮKassa / Тинькофф)
- Отчёты и аналитика

---

**Лицензия:** MIT

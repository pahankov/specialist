# Online Booking — Система онлайн-записи

Приложение для онлайн-записи клиентов на услуги через веб-интерфейс. Клиент выбирает мастера, услугу и время — мастер управляет записями через админ-панель.

## 🚀 Быстрый старт

### Требования

- **Python** 3.11+
- **Node.js** 20+
- **PostgreSQL** 16 (production, через Docker)

### Запуск

**Быстрый запуск (Windows):**

```
start.bat              # Backend + Frontend
run_backend.bat        # Только backend
run_frontend.bat       # Только frontend
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

## 📦 Структура проекта

```
online-booking/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI приложение (lifespan, router registration)
│   │   ├── config.py         # Настройки (SQLite/PostgreSQL, JWT, refresh tokens)
│   │   ├── database.py       # Подключение к БД (aiosqlite / asyncpg)
│   │   ├── logging_config.py # Цветное логирование (ANSI) + rotating file handler
│   │   ├── dependencies/     # Общие зависимости (зависят от моделей)
│   │   │   ├── auth.py       # JWT: get_current_user, require_master, require_admin
│   │   │   └── crud.py       # CRUD: get_or_404, get_owned_or_404, soft_delete
│   │   ├── middleware/       # Мидлвари
│   │   │   └── rate_limit.py # RateLimiter (60 req/min default)
│   │   ├── services/         # Бизнес-логика (зависят от БД)
│   │   │   ├── audit.py      # Audit logging (логирование действий)
│   │   │   ├── sms/          # SMS провайдеры (FakeSmsProvider, Twilio, SMS.ru)
│   │   │   ├── cache.py      # Redis cache (dashboard stats, graceful degradation)
│   │   │   ├── background_tasks.py  # RQ background task queue (CSV export)
│   │   │   └── export_tasks.py     # Background export functions
│   │   ├── models/           # SQLAlchemy ORM (User, MasterProfile, ClientProfile, Country, City, OtpCode + др.)
│   │   ├── schemas/          # Pydantic schemas (request/response validation)
│   │   │   ├── pagination.py # PaginatedResponse[T] — generic пагинация со total count
│   │   ├── utils/            # Утилиты (timezone, formatPhone)
│   │   └── modules/          # Модульная архитектура (self-contained packages)
│   │       ├── auth/         # Регистрация, логин, JWT, OTP, refresh token rotation
│   │       │   ├── router.py         # Эндпоинты: register, login, send-otp, verify-otp, refresh, logout
│   │       │   ├── service.py        # Бизнес-логика: register_master, login_master, send_otp, verify_otp
│   │       │   ├── token.py          # JWT: create_access_token, create_refresh_token
│   │       │   ├── dependencies.py   # JWT зависимости: get_current_user, require_master, require_admin
│   │       │   └── schemas.py        # TokenResponse, TokenRefreshResponse
│   │       ├── city/         # Страны и города (CRUD + поиск)
│   │       │   ├── router.py         # Эндпоинты: get_countries, get_cities
│   │       ├── user/         # CRUD мастеров и клиентов (через User + MasterProfile/ClientProfile)
│   │       ├── booking/      # CRUD записей + публичная запись
│   │       ├── service/      # CRUD услуг
│   │       ├── schedule/     # Рабочее расписание
│   │       ├── review/       # Отзывы и рейтинги
│   │       └── admin/        # Админ-панель (17 эндпоинт-модулей)
│   ├── alembic/              # Alembic миграции для PostgreSQL
│   ├── alembic.ini           # Конфиг Alembic
│   ├── tests/                # pytest тесты (135 тестов: auth, masters, services, appointments, clients, reviews, admin CRUD, rate limiting, refresh tokens, password security, no-show)
│   ├── requirements.txt      # Зависимости Python
│   └── pyproject.toml        # Конфиг pytest
├── frontend/
│   ├── src/
│   │   ├── api/              # API клиент (axios с auth-interceptor, refresh queue, httpOnly cookies)
│   │   ├── components/       # Общие компоненты (Modal, Pagination, FilterBar, MessageBar, Toast, ReviewsSection)
│   │   ├── pages/            # Публичные + админ-панель (12 страниц)
│   │   ├── tests/            # Vitest автотесты (44 теста)
│   │   ├── utils/            # Утилиты (formatPhone — единый форматировщик телефонов)
│   │   ├── App.tsx           # Роутинг
│   │   └── main.tsx          # Точка входа
│   ├── package.json
│   ├── vitest.config.ts      # Vitest конфиг
│   ├── .eslintrc.cjs         # ESLint конфиг
│   └── .prettierrc           # Prettier конфиг
├── docker-compose.yml        # Docker-конфиг (PostgreSQL + Redis, production)
├ .env.example                # Шаблон переменных окружения
├ start.bat                   # Запуск backend + frontend (Windows)
├ run_backend.bat             # Запуск backend только (Windows)
└── run_frontend.bat          # Запуск frontend только (Windows)
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
| Auth | JWT (python-jose), bcrypt==4.3.0 (passlib), refresh token rotation, httpOnly cookies |
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
- **Backend:** 135 pytest-тестов (auth, masters, services, appointments, clients, reviews, admin CRUD, rate limiting, refresh tokens, password security, no-show)
- **Frontend:** 44 Vitest-теста (helpers, hooks, Modal, MessageBar, Pagination, FilterBar)
- 100% покрытие всех эндпоинтов
- In-memory SQLite для изоляции тестов
- pytest-asyncio для асинхронных тестов
- @testing-library/react для компонентных тестов

## 🔌 API Endpoints

### Auth
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/register` | Регистрация мастера (с выбором города) |
| `POST` | `/api/v1/auth/login` | Вход мастера (JWT + refresh token в cookies) |
| `POST` | `/api/v1/auth/send-otp` | Отправка SMS-кода клиенту |
| `POST` | `/api/v1/auth/verify-otp` | Проверка кода, вход/регистрация клиента |
| `POST` | `/api/v1/auth/refresh` | Обновление access token (refresh token rotation) |
| `POST` | `/api/v1/auth/logout` | Выход (очистка cookies) |
| `POST` | `/api/v1/auth/client/login` | Legacy вход клиента по телефону |

### Geography
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/countries/` | Список стран |
| `GET` | `/api/v1/cities/` | Список городов (пагинация, поиск, фильтр по стране) |
| `GET` | `/api/v1/cities/{id}` | Город по ID |

### Masters
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/masters/` | Список мастеров (пагинация) |
| `GET` | `/api/v1/masters/{id}` | Мастер по ID |
| `POST` | `/api/v1/masters/` | Создать мастера |
| `PATCH` | `/api/v1/masters/{id}` | Обновить мастера |
| `DELETE` | `/api/v1/masters/{id}` | Удалить мастера |

### Services
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/services/` | Список услуг (пагинация) |
| `GET` | `/api/v1/services/{id}` | Услуга по ID |
| `POST` | `/api/v1/services/` | Создать услугу |
| `DELETE` | `/api/v1/services/{id}` | Удалить услугу |

### Appointments
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/appointments/` | Список записей |
| `POST` | `/api/v1/appointments/` | Создать запись |
| `POST` | `/api/v1/appointments/public` | Публичная запись с conflict-check (409 при пересечении) |
| `GET` | `/api/v1/appointments/available-days` | Доступные дни |
| `GET` | `/api/v1/appointments/available-slots` | Доступные слоты |
| `DELETE` | `/api/v1/appointments/{id}` | Удалить запись |

### Clients
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/clients/` | Список клиентов |
| `GET` | `/api/v1/clients/{id}` | Клиент по ID |
| `POST` | `/api/v1/clients/` | Создать клиента |
| `DELETE` | `/api/v1/clients/{id}` | Удалить клиента |

### Working Hours
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/working-hours/` | Расписание |
| `POST` | `/api/v1/working-hours/` | Добавить расписание |
| `DELETE` | `/api/v1/working-hours/{id}` | Удалить расписание |

### Admin (JWT required, master-scoped)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/admin/dashboard` | Статистика (записи, клиенты, доход) |
| `GET` | `/admin/monthly-stats` | Статистика за месяц |
| `GET` | `/admin/appointments` | Список записей (пагинация, фильтрация) |
| `POST` | `/admin/appointments` | Создать запись |
| `POST` | `/admin/appointments/book` | Админская запись (выбор клиента из БД) |
| `GET` | `/admin/appointments/by-date` | Записи по дате |
| `PATCH` | `/admin/appointments/{id}/confirm` | Подтвердить запись |
| `PATCH` | `/admin/appointments/{id}/cancel` | Отменить запись |
| `PATCH` | `/admin/appointments/{id}/complete` | Завершить запись |
| `DELETE` | `/admin/appointments/{id}` | Удалить запись |
| `GET` | `/admin/services` | Список активных услуг |
| `GET` | `/admin/services/all` | Список всех услуг (включая неактивные) |
| `POST` | `/admin/services` | Создать услугу |
| `PATCH` | `/admin/services/{id}` | Обновить услугу |
| `DELETE` | `/admin/services/{id}` | Soft-delete услуги |
| `GET` | `/admin/clients` | Список клиентов |
| `POST` | `/admin/clients` | Создать клиента |
| `PATCH` | `/admin/clients/{id}` | Обновить клиента |
| `DELETE` | `/admin/clients/{id}` | Удалить клиента |
| `GET` | `/admin/working-hours` | Расписание |
| `POST` | `/admin/working-hours` | Добавить рабочий день |
| `PATCH` | `/admin/working-hours/{id}` | Обновить рабочий день |
| `DELETE` | `/admin/working-hours/{id}` | Удалить рабочий день |
| `GET` | `/admin/audit-logs` | Журнал действий (пагинация, фильтрация) |
| `GET` | `/admin/export/appointments` | Экспорт записей в CSV |
| `GET` | `/admin/export/clients` | Экспорт клиентов в CSV |
| `GET` | `/admin/blocked-slots` | Заблокированные слоты |
| `POST` | `/admin/blocked-slots` | Заблокировать слот |
| `DELETE` | `/admin/blocked-slots/{id}` | Убрать блокировку |

### Superadmin (JWT required, is_admin=true)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/admin/masters` | Список всех мастеров (фильтры: поиск, is_active, is_admin) |
| `GET` | `/admin/masters/{id}` | Мастер по ID |
| `POST` | `/admin/masters` | Создать мастера |
| `PATCH` | `/admin/masters/{id}` | Обновить мастера |
| `DELETE` | `/admin/masters/{id}` | Удалить мастера |
| `POST` | `/admin/masters/{id}/toggle-active` | Блокировка/разблокировка мастера |
| `GET` | `/admin/masters/{id}/full` | Полная карточка (статистика, рейтинг, отзывы, записи) |
| `POST` | `/admin/masters/{id}/suspend` | Заблокировать навсегда |
| `POST` | `/admin/masters/{id}/unsuspend` | Разблокировать |
| `GET` | `/admin/masters/{id}/stats` | Статистика по мастеру |
| `POST` | `/admin/masters/bulk/toggle-active` | Массовая смена статуса |
| `POST` | `/admin/masters/bulk/suspend` | Массовая блокировка |
| `POST` | `/admin/masters/bulk/unsuspend` | Массовая разблокировка |
| `POST` | `/admin/masters/import` | Импорт мастеров из CSV |
| `GET` | `/admin/reviews` | Все отзывы (пагинация, фильтры: master_id, is_published) |
| `GET` | `/admin/reviews/average/{master_id}` | Средний рейтинг мастера |
| `PATCH` | `/admin/reviews/{id}/publish` | Опубликовать отзыв |
| `PATCH` | `/admin/reviews/{id}/unpublish` | Скрыть отзыв |
| `DELETE` | `/admin/reviews/{id}` | Удалить отзыв |
| `GET` | `/admin/audit-logs?master_id=X` | Логи действий (фильтр по мастеру) |
| `GET` | `/admin/global-stats` | Глобальная статистика по всей системе |
| `POST` | `/admin/dashboard/cache/clear` | Сброс кэша дашборда |

### Health & Changelog
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/health` | Быстрая проверка (без БД) |
| `GET` | `/admin/health` | Полная проверка (DB + Redis cache + RQ) |
| `GET` | `/admin/health/verbose` | Расширенная (метрики БД, статистика RQ) |
| `GET` | `/admin/changelog` | История версий API |

### Reviews (публичные + авторизованные)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/reviews/` | Список опубликованных отзывов (фильтр по master_id) |
| `GET` | `/api/v1/reviews/average` | Средний рейтинг мастера |
| `POST` | `/api/v1/reviews/` | Создать отзыв (только на completed appointment) |
| `PATCH` | `/api/v1/reviews/{id}` | Обновить отзыв (comment, publish) |
| `DELETE` | `/api/v1/reviews/{id}` | Удалить отзыв |

### Admin No-Show
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `PATCH` | `/admin/appointments/{id}/no-show` | Отметить запись как неявку |

## 🔐 Админ-панель

**Обычный мастер** (любой зарегистрированный мастер):
- Вход: `/admin/login` — используйте email и пароль зарегистрированного мастера.
- Видит только свои данные: свои записи, свои услуги, своих клиентов.

**Суперпользователь** (мастер с `is_admin=true`):
- Вход: тот же `/admin/login` — но видит все данные системы.
- **Дашборд** — глобальная статистика (все мастера, все записи, все клиенты, общий доход)
- **Мастера** — управление мастерами:
  - Поиск и фильтрация (по имени/email, статус, роль)
  - Создание, редактирование, удаление мастеров
  - Массовые операции: bulk toggle active, bulk suspend/unsuspend
  - Импорт из CSV
  - Детальная карточка: статистика, рейтинг, отзывы, последние записи, история действий
  - Блокировка/разблокировка мастеров (active/inactive/suspended)
  - Просмотр статистики по каждому мастеру
- **Записи** — видит все записи всех мастеров, пагинация, фильтрация
- **Клиенты** — видит всех клиентов системы, пагинация, поиск
- **Услуги** — пагинация, фильтрация по активности
- **Отзывы** — модерация: approve, unpublish, delete, средний рейтинг
- **Глобальная статистика** — карточки с метриками, breakdown по статусам, последние записи
- **Логи** — журнал всех действий с фильтрацией по мастеру
- **Экспорт** — CSV с фоновой обработкой (RQ), статус задач
- **Health check** — проверка DB, Redis cache, RQ queue

**Различие ролей:**
| Функция | Мастер | Суперпользователь |
|---------|--------|-------------------|
| Дашборд | Свои записи, клиенты, услуги | Всё по системе |
| Записи | Только свои | Все записи |
| Услуги | Только свои | — |
| Мастера | — | CRUD + права + блокировка |
| Статистика | Своя | Глобальная |
| Навигация | Дашборд, Записи, Услуги, Клиенты, Расписание | Дашборд, Мастера, Все записи, Все клиенты, Расписание, Логи |

## 🗄️ База данных

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

### Статусы записей
- `pending` — ожидает подтверждения
- `confirmed` — подтверждена
- `cancelled` — отменена
- `completed` — завершена

## 🔒 Безопасность

 1. **Пароли:** Bcrypt hashing (passlib), валидация: min 8 символов, 1 заглавная, 1 строчная, 1 цифра, 1 спецсимвол (!@#$%^&* и т.д.), 4 уникальных символа
 2. **Аутентификация:** JWT токены (python-jose, HS256) + refresh token rotation
 3. **SMS OTP:** 6-значный код на телефон (TTL 5 мин), hash-хранение кода, поддержка Twilio/SMS.ru
 4. **Cookies:** refresh_token — `httponly=True` (только HTTP), access_token — `httponly=False` (читается JS)
 5. **Rate limiting:** 60 req/min default, 10 req/min для auth-эндпоинтов
 6. **Валидация:** Pydantic schemas с проверкой типов
 7. **SQL-инъекции:** Защищено SQLAlchemy ORM
 8. **Логирование:** Цветной вывод в консоль (ANSI), SQL-запросы на уровне WARNING, файлы логов с ротацией

## 🧪 Тесты

```powershell
# Backend
cd backend
$env:PYTHONPATH='.'
pytest tests/ -v                          # Все тесты (135)
pytest tests/test_reviews.py -v           # Только reviews
pytest tests/ -v --cov=app                # С покрытием

# Frontend
cd frontend
npx vitest run                            # Все тесты (44)
npx vitest run src/tests/helpers.test.ts  # Только helpers
npx vitest                              # Watch mode
```

## 🌱 Seed-скрипт

Создание суперпользователя:

```powershell
cd backend
$env:PYTHONPATH='.'
python create_superuser.py
```

## 🐛 Решение проблем

### Backend не запускается
```powershell
cd backend
pip install -r requirements.txt
```

### Frontend не подгружается
```powershell
cd frontend
Remove-Item -Recurse -Force node_modules
npm install
npm run dev
```

### Порт уже занят
```powershell
# Найти процесс на порту 8000
netstat -ano | findstr :8000

# Убить процесс (Windows)
taskkill /PID <PID> /F
```

## 📋 Логирование

Приложение использует стандартную систему логирования Python с 5 уровнями:

| Уровень | Описание |
|---------|----------|
| `DEBUG` | Отладочная информация (разработчик) |
| `INFO` | Информационные сообщения о штатной работе |
| `WARNING` | Предупреждения о нештатных ситуациях |
| `ERROR` | Ошибки выполнения операций |
| `CRITICAL` | Критические ошибки, угрожающие работе приложения |

**Конфигурация:** `backend/app/logging_config.py`

**Вывод:**
- **Console** → `stderr` (базовый уровень из конфига)
- **File** → `backend/logs/app.log` (всё, включая DEBUG)
- **Rotating** → автоархивация при 10 МБ, 5 файлов

**Примеры логов:**
```
[2026-09-20 20:54:59] INFO app.api.auth: Запрос на регистрацию мастера: test@example.com
[2026-09-20 20:54:59] WARNING app.api.auth: Регистрация заблокирована — мастер уже существует
[2026-09-20 20:54:59] ERROR app.api.appointments: Запись не найдена: id=999
[2026-09-20 20:54:59] CRITICAL root: Критическая ошибка
```

## 📝 Примеры API (curl)

### Регистрация мастера
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Елена","email":"elena@example.com","password":"SecurePass123!","phone":"+79991234567","telegram_username":"elena_sugar"}'
```

### Создание суперпользователя
```powershell
cd backend
$env:PYTHONPATH='.'
python create_superuser.py
# Создаёт: pahankov@mail.ru / Sug@r2026! (role=admin)
```

### Логин мастера (возвращает cookies)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"elena@example.com","password":"SecurePass123!"}'
```

### OTP: отправка кода клиенту
```bash
curl -X POST http://localhost:8000/api/v1/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79991234567"}'
```

### OTP: проверка кода
```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79991234567","code":"A1B2C3"}'
```

### Обновление токена
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh
```

### Выход (очистка cookies)
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout
```

### Список городов
```bash
curl -X GET "http://localhost:8000/api/v1/cities/?country_id=1&page=1&page_size=50"
```

### Создание услуги
```bash
curl -X POST http://localhost:8000/api/v1/services/ \
  -H "Content-Type: application/json" \
  -d '{"master_id":1,"name":"Шугаринг ног полностью","description":"Удаление волос на ногах","duration_minutes":60,"price":2500}'
```

### Публичная запись (с conflict-check)
```bash
curl -X POST http://localhost:8000/api/v1/appointments/public \
  -H "Content-Type: application/json" \
  -d '{"master_id":1,"service_id":1,"client_name":"Иван","client_phone":"9991234567","appointment_date":"2026-09-20T14:00:00"}'
```

### Управление мастерами (суперпользователь)
```bash
# Список всех мастеров
curl -X GET http://localhost:8000/api/v1/admin/masters/

# Поиск мастеров
curl -X GET "http://localhost:8000/api/v1/admin/masters/?search=Елена&is_active=true&is_admin=false"

# Создать мастера
curl -X POST http://localhost:8000/api/v1/admin/masters/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Мария","email":"maria@example.com","password":"SecurePass456!","phone":"+79991234568"}'

# Блокировка мастера
curl -X POST http://localhost:8000/api/v1/admin/masters/1/toggle-active

# Назначение прав суперпользователя
curl -X POST http://localhost:8000/api/v1/admin/masters/1/toggle-admin

# Статистика по мастеру
curl -X GET http://localhost:8000/api/v1/admin/masters/1/stats
```

### Глобальная статистика (суперпользователь)
```bash
curl -X GET http://localhost:8000/api/v1/admin/global-stats
```

### Отзывы и рейтинги
```bash
# Список отзывов
curl -X GET "http://localhost:8000/api/v1/reviews/?master_id=1"

# Средний рейтинг
curl -X GET "http://localhost:8000/api/v1/reviews/average?master_id=1"

# Создать отзыв
curl -X POST http://localhost:8000/api/v1/reviews/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"appointment_id":1,"rating":5.0,"comment":"Отличный мастер!"}'

# Обновить отзыв
curl -X PATCH http://localhost:8000/api/v1/reviews/1 \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"comment":"Обновлённый комментарий","is_published":true}'

# Удалить отзыв
curl -X DELETE http://localhost:8000/api/v1/reviews/1 \
  -H "Authorization: Bearer <token>"
```

### No-show tracking
```bash
# Отметить запись как неявку
curl -X PATCH http://localhost:8000/api/v1/admin/appointments/1/no-show \
  -H "Authorization: Bearer <token>"
```

### Health check
```bash
# Быстрая проверка
curl -X GET http://localhost:8000/health

# Полная проверка (DB + Redis + RQ)
curl -X GET http://localhost:8000/api/v1/admin/health

# Расширенная (с метриками)
curl -X GET http://localhost:8000/api/v1/admin/health/verbose
```

### API Changelog
```bash
# История версий API
curl -X GET http://localhost:8000/api/v1/admin/changelog
```

### Admin reviews
```bash
# Список всех отзывов (пагинация)
curl -X GET "http://localhost:8000/api/v1/admin/reviews?page=1&page_size=20"

# Фильтр по мастеру
curl -X GET "http://localhost:8000/api/v1/admin/reviews?master_id=1&is_published=true"

# Опубликовать отзыв
curl -X PATCH http://localhost:8000/api/v1/admin/reviews/1/publish \
  -H "Authorization: Bearer <token>"

# Скрыть отзыв
curl -X PATCH http://localhost:8000/api/v1/admin/reviews/1/unpublish \
  -H "Authorization: Bearer <token>"

# Удалить отзыв
curl -X DELETE http://localhost:8000/api/v1/admin/reviews/1 \
  -H "Authorization: Bearer <token>"

# Средний рейтинг мастера
curl -X GET "http://localhost:8000/api/v1/admin/reviews/average/1"
```

### Master detail (full profile)
```bash
# Полная карточка мастера (статистика, рейтинг, отзывы, записи)
curl -X GET http://localhost:8000/api/v1/admin/masters/1/full \
  -H "Authorization: Bearer <token>"
```

### Bulk operations
```bash
# Массовая смена статуса
curl -X POST http://localhost:8000/api/v1/admin/masters/bulk/toggle-active \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '[1, 2, 3]'

# Массовая блокировка
curl -X POST http://localhost:8000/api/v1/admin/masters/bulk/suspend \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '[1, 2, 3]'
```

### Master import from CSV
```bash
# Импорт мастеров из CSV (name,email,password,phone,telegram_username)
curl -X POST http://localhost:8000/api/v1/admin/masters/import \
  -H "Authorization: Bearer <token>" \
  -F "file=@masters.csv"
```

### Background export
```bash
# Запуск фонового экспорта
curl -X POST "http://localhost:8000/api/v1/admin/export/appointments?background=true&status=pending" \
  -H "Authorization: Bearer <token>"

# Статус задачи
curl -X GET http://localhost:8000/api/v1/admin/export/appointments/status/<job_id> \
  -H "Authorization: Bearer <token>"

# Статистика очереди задач
curl -X GET http://localhost:8000/api/v1/admin/export/stats \
  -H "Authorization: Bearer <token>"
```

### Audit logs by master
```bash
# Логи действий по конкретному мастеру
curl -X GET "http://localhost:8000/api/v1/admin/audit-logs?master_id=1&page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

## 📚 История версий

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
- **Фикс бэкапа:** `start.bat` — автоматический бэкап БД перед запуском
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

# Sugar Booking — Система записи на шугаринг

Приложение для записи клиентов к мастеру шугаринга через веб-интерфейс. Клиент выбирает мастера, услугу и время — мастер управляет записями через админ-панель.

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
cd backend
$env:PYTHONPATH='.'
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

**Frontend:**
```powershell
cd frontend
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
sugar-booking/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI приложение (lifespan, router registration)
│   │   ├── config.py         # Настройки (SQLite/PostgreSQL, JWT, refresh tokens)
│   │   ├── database.py       # Подключение к БД (aiosqlite / asyncpg)
│   │   ├── middleware.py     # Rate limiting middleware
│   │   ├── models/           # SQLAlchemy ORM models (10 сущностей + RefreshToken)
│   │   ├── schemas/          # Pydantic schemas (request/response validation)
│   │   └── modules/          # Модульная архитектура (self-contained packages)
│   │       ├── auth/         # Регистрация, логин, JWT, refresh token rotation
│   │       │   ├── router.py         # Эндпоинты: register, login, refresh, logout
│   │       │   ├── service.py        # Бизнес-логика: register_master, login_master
│   │       │   ├── token.py          # JWT: create_access_token, create_refresh_token
│   │       │   ├── dependencies.py   # JWT зависимости: get_current_master, require_super_admin
│   │       │   └── schemas.py        # TokenResponse, TokenRefreshResponse
│   │       ├── user/         # CRUD мастеров и клиентов
│   │       ├── booking/      # CRUD записей + публичная запись
│   │       ├── service/      # CRUD услуг
│   │       ├── schedule/     # Рабочее расписание
│   │       ├── review/       # Отзывы и рейтинги
│   │       └── admin/        # Админ-панель (12 эндпоинт-модулей)
│   ├── alembic/              # Alembic миграции для PostgreSQL
│   ├── alembic.ini           # Конфиг Alembic
│   ├── tests/                # pytest тесты (135 тестов: auth, masters, services, appointments, clients, reviews, admin CRUD, rate limiting, refresh tokens, password security, no-show)
│   ├── requirements.txt      # Зависимости Python
│   └── pyproject.toml        # Конфиг pytest
├── frontend/
│   ├── src/
│   │   ├── api/              # API клиент (axios с auth-interceptor, refresh queue, httpOnly cookies)
│   │   ├── components/       # Общие компоненты (Modal, Pagination, FilterBar, MessageBar, ReviewsSection)
│   │   ├── pages/            # Публичные + админ-панель (12 страниц)
│   │   ├── tests/            # Vitest автотесты (44 теста)
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
| Frontend | React 18, TypeScript 5, Vite 6 |
| HTTP | Axios (interceptors, refresh queue) |
| Тесты | pytest, pytest-asyncio, httpx, Vitest, @testing-library/react |
| Линтинг | ESLint + Prettier |
| Production DB | PostgreSQL 16 |
| Production cache | Redis 7 |
| Rate limiting | Встроенный middleware (60 req/min default) |

## 📋 Что реализовано

### ✅ Backend
- Регистрация и аутентификация мастера (JWT + refresh token rotation)
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
- Пагинация: мастера, клиенты, услуги (limit/offset, 1-200)
- Валидация пароля: min 8 символов, 1 заглавная, 1 строчная, 1 цифра, 1 спецсимвол, 4 уникальных символа
- Валидация телефона: 10 цифр, автоформатирование в +7 (XXX) XXX-XX-XX
- Alembic миграции для PostgreSQL
- Авто-создание таблиц для SQLite через `create_all` в lifespan
- Swagger UI документация (`/docs`)
- Health check эндпоинт (`/health`)
- Rate limiting middleware (60 req/min default, 10 req/min для auth)
- No-show tracking: счётчик неяв клиентов, эндпоинт `/admin/appointments/{id}/no-show`
- Отзывы и рейтинги: CRUD отзывов, средний рейтинг, публичная страница отзывов

### ✅ Frontend
- Главная страница (список мастеров и услуг)
- Страница бронирования с проверкой конфликтов
- Админ-панель (12 страниц):
  - Дашборд — статистика записей, клиентов, услуг, доход
  - Записи — фильтрация по статусу, пагинация, подтверждение, завершение, отмена, удаление, no-show
  - Услуги — создание, редактирование, soft-delete, пагинация
  - Клиенты — создание, редактирование, удаление, экспорт CSV, пагинация
  - Расписание — Calendar, TimeSlots, BookingModal, MonthlyStats (рефакторинг из монолита)
  - Логи — журнал всех действий с фильтрацией и пагинацией
  - Мастера — управление мастерами (CRUD, блокировка, назначение прав суперпользователя) [суперпользователь]
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
| `POST` | `/api/v1/auth/register` | Регистрация мастера |
| `POST` | `/api/v1/auth/login` | Вход (JWT + refresh token в cookies) |
| `POST` | `/api/v1/auth/refresh` | Обновление access token (refresh token rotation) |
| `POST` | `/api/v1/auth/logout` | Выход (очистка cookies) |

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
| `POST` | `/admin/masters/{id}/toggle-admin` | Назначение/снятие прав суперпользователя |
| `GET` | `/admin/masters/{id}/stats` | Статистика по мастеру |
| `GET` | `/admin/global-stats` | Глобальная статистика по всей системе |

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
  - Блокировка/разблокировка мастеров
  - Назначение/снятие прав суперпользователя
  - Просмотр статистики по каждому мастеру
- **Записи** — видит все записи всех мастеров
- **Клиенты** — видит всех клиентов системы
- **Глобальная статистика** — карточки с метриками, breakdown по статусам, последние записи
- **Логи** — журнал всех действий

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
Master (id, name, email, phone, telegram_username, hashed_password, is_admin, is_active, avatar_url, timezone.utc)
  ├─ 1:N ──> Service (id, master_id, name, description, duration_minutes, price, is_active, cascade delete)
  │           └─ 1:N ──> Appointment
  ├─ 1:N ──> Appointment (id, master_id, service_id, client_id, appointment_date, status, notes, cascade delete)
  │           └─ N:1 ──> Client
  │           └─ N:1 ──> Service
  ├─ 1:N ──> WorkingHour (id, master_id, schedule_date[Date], start_time, end_time)
  ├─ 1:N ──> AuditLog (id, master_id, action, entity_type, entity_id, details, ip_address, created_at)
  ├─ 1:N ──> BlockedSlot (id, master_id, start_dt, end_dt, reason, created_at)
  └─ 1:N ──> RefreshToken (id, master_id, token_jti, expires_at, is_revoked, cascade delete)

Client (id, name, phone, email, created_at, unique phone)
  └─ 1:N ──> Appointment

RefreshToken (id, master_id, token_jti, token_hash, expires_at, is_revoked, created_at, used_for_rotation)
```

### Статусы записей
- `pending` — ожидает подтверждения
- `confirmed` — подтверждена
- `cancelled` — отменена
- `completed` — завершена

## 🔒 Безопасность

 1. **Пароли:** Bcrypt hashing (passlib), валидация: min 8 символов, 1 заглавная, 1 строчная, 1 цифра, 1 спецсимвол (!@#$%^&* и т.д.), 4 уникальных символа
 2. **Аутентификация:** JWT токены (python-jose, HS256) + refresh token rotation
 3. **Cookies:** access_token — `httponly=False` (читается JS), refresh_token — `httponly=True` (только HTTP)
 4. **Rate limiting:** 60 req/min default, 10 req/min для auth-эндпоинтов
 5. **Валидация:** Pydantic schemas с проверкой типов
 6. **SQL-инъекции:** Защищено SQLAlchemy ORM
 7. **Логирование:** Цветной вывод в консоль (ANSI), SQL-запросы на уровне WARNING, файлы логов с ротацией

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
# Создаёт: pahankov@mail.ru / Sug@r2026! (is_admin=true)
```

### Логин (возвращает cookies)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"elena@example.com","password":"SecurePass123!"}'
```

### Обновление токена
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh
```

### Выход (очистка cookies)
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout
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

## 📚 История версий

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

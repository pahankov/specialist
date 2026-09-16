# Sugar Booking — Система записи на шугаринг

Приложение для записи клиентов к мастеру шугаринга через веб-интерфейс. Клиент выбирает мастера, услугу и время — мастер управляет записями через админ-панель.

## 🚀 Быстрый старт

### Требования

- **Python** 3.11+
- **Node.js** 20+

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

## 📦 Структура проекта

```
sugar-booking/
├── backend/
│   ├── app/
│   │   ├── api/              # REST endpoints (auth, masters, services, appointments, clients, working_hours, admin)
│   │   ├── models/           # SQLAlchemy ORM models (5 сущностей)
│   │   ├── schemas/          # Pydantic schemas (request/response validation)
│   │   ├── config.py         # Настройки (SQLite, JWT)
│   │   ├── database.py       # Подключение к БД (aiosqlite)
│   │   └── main.py           # FastAPI приложение
│   ├── tests/                # pytest тесты (18 тестов: auth + masters CRUD)
│   ├── requirements.txt      # Зависимости Python
│   └── pyproject.toml        # Конфиг pytest
├── frontend/
│   ├── src/
│   │   ├── api/              # API клиент (axios)
│   │   ├── pages/            # 8 страниц (публичные + админ-панель)
│   │   ├── App.tsx           # Роутинг
│   │   └── main.tsx          # Точка входа
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml        # Docker-конфиг (PostgreSQL + Redis, production)
├── start.bat                 # Запуск backend + frontend (Windows)
├── run_backend.bat           # Запуск backend только (Windows)
└── run_frontend.bat          # Запуск frontend только (Windows)
```

## 🛠 Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Backend | FastAPI 0.115, SQLAlchemy 2.0 (async), aiosqlite |
| Auth | JWT (python-jose), bcrypt (passlib) |
| Frontend | React 18, TypeScript 5, Vite 6 |
| HTTP | Axios |
| Тесты | pytest, pytest-asyncio, httpx |
| Production DB | PostgreSQL 16 |
| Production cache | Redis 7 |

## 📋 Что реализовано

### ✅ Backend
- Регистрация и аутентификация мастера (JWT)
- CRUD мастеров (создание, чтение, обновление, удаление)
- CRUD услуг
- CRUD записей (создание, отмена)
- Публичная запись без авторизации
- Расчёт доступных дней и слотов
- Управление клиентами (автоматическое создание при записи)
- Управление рабочим расписанием
- Swagger UI документация (`/docs`)

### ✅ Frontend
- Главная страница (список мастеров и услуг)
- Страница бронирования
- Админ-панель (8 страниц):
  - Дашборд — статистика записей, клиентов, услуг, доход
  - Записи — фильтрация по статусу, подтверждение, отмена
  - Услуги — создание, редактирование, удаление
  - Расписание — управление рабочими часами
- Адаптивный дизайн

### ✅ Тесты
- 18 pytest-тестов (auth + masters CRUD)
- In-memory SQLite для изоляции тестов
- pytest-asyncio для асинхронных тестов

## 🔌 API Endpoints

### Auth
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/register` | Регистрация мастера |
| `POST` | `/api/v1/auth/login` | Вход (JWT токен) |

### Masters
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/masters/` | Список мастеров |
| `GET` | `/api/v1/masters/{id}` | Мастер по ID |
| `POST` | `/api/v1/masters/` | Создать мастера |
| `PATCH` | `/api/v1/masters/{id}` | Обновить мастера |
| `DELETE` | `/api/v1/masters/{id}` | Удалить мастера |

### Services
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/services/` | Список услуг |
| `GET` | `/api/v1/services/{id}` | Услуга по ID |
| `POST` | `/api/v1/services/` | Создать услугу |
| `DELETE` | `/api/v1/services/{id}` | Удалить услугу |

### Appointments
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/appointments/` | Список записей |
| `POST` | `/api/v1/appointments/` | Создать запись |
| `POST` | `/api/v1/appointments/public` | Публичная запись (без авторизации) |
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

### Admin (JWT required)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/admin/dashboard` | Статистика (записи, клиенты, доход) |
| `GET` | `/admin/appointments` | Список записей |
| `PATCH` | `/admin/appointments/{id}/confirm` | Подтвердить запись |
| `PATCH` | `/admin/appointments/{id}/cancel` | Отменить запись |
| `GET` | `/admin/appointments/by-date` | Записи по дате |
| `POST` | `/admin/services` | Создать услугу |
| `PATCH` | `/admin/services/{id}` | Обновить услугу |
| `DELETE` | `/admin/services/{id}` | Удалить услугу |
| `GET` | `/admin/working-hours` | Расписание |
| `POST` | `/admin/working-hours` | Добавить рабочий день |
| `DELETE` | `/admin/working-hours/{id}` | Удалить рабочий день |

## 🔐 Админ-панель

Вход: `/admin/login` — используйте email и пароль зарегистрированного мастера.

Функции:
- **Дашборд** — статистика записей, клиентов, услуг, доход
- **Записи** — фильтрация по статусу, подтверждение, отмена
- **Услуги** — создание, редактирование, удаление
- **Расписание** — управление рабочими часами

## 🗄️ База данных

**Локальная разработка:** SQLite (aiosqlite) — таблицы создаются автоматически при старте.

**Production:** PostgreSQL 16 (через Docker Compose).

### Сущности

```
Master (id, name, email, phone, telegram_username, hashed_password, ...)
  ├─ 1:N ──> Service (id, master_id, name, description, duration_minutes, price)
  │           └─ 1:N ──> Appointment
  ├─ 1:N ──> Appointment (id, master_id, service_id, client_id, appointment_date, status, notes)
  ├─ 1:N ──> WorkingHour (id, master_id, day_of_week, start_time, end_time)

Client (id, name, phone, email, created_at)
  └─ 1:N ──> Appointment
```

### Статусы записей
- `pending` — ожидает подтверждения
- `confirmed` — подтверждена
- `cancelled` — отменена
- `completed` — завершена

## 🔒 Безопасность

1. **Пароли:** Bcrypt hashing (passlib)
2. **Аутентификация:** JWT токены (python-jose, HS256)
3. **Валидация:** Pydantic schemas с проверкой типов
4. **SQL-инъекции:** Защищено SQLAlchemy ORM

## 🧪 Тесты

```powershell
cd backend
$env:PYTHONPATH='.'
pytest tests/ -v                          # Все тесты
pytest tests/test_auth.py -v              # Только auth
pytest tests/test_masters.py -v           # Только masters
pytest tests/ -v --cov=app                # С покрытием
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

## 📝 Примеры API (curl)

### Регистрация мастера
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Елена","email":"elena@example.com","password":"SecurePass123!","phone":"+79991234567","telegram_username":"elena_sugar"}'
```

### Логин
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login?email=elena@example.com&password=SecurePass123!"
```

### Создание услуги
```bash
curl -X POST http://localhost:8000/api/v1/services/ \
  -H "Content-Type: application/json" \
  -d '{"master_id":1,"name":"Шугаринг ног полностью","description":"Удаление волос на ногах","duration_minutes":60,"price":2500}'
```

### Публичная запись
```bash
curl -X POST http://localhost:8000/api/v1/appointments/public \
  -H "Content-Type: application/json" \
  -d '{"master_id":1,"service_id":1,"client_name":"Иван","client_phone":"+79991234567","appointment_date":"2026-09-20T14:00:00"}'
```

## 📚 История версий

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
- Миграция на PostgreSQL (Alembic)
- CI/CD (GitHub Actions)
- Frontend-тесты (Vitest)
- Деплой (Nginx, HTTPS)

---

**Лицензия:** MIT

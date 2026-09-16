# Sugar Booking — Система записи на шугаринг

Приложение для записи клиентов к мастеру шугаринга через веб-интерфейс.

## 🚀 Быстрый старт

### Требования

- **Python** 3.11+
- **Node.js** 20+
- **pip** (для управления зависимостями)

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
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas (request/response validation)
│   │   ├── config.py         # Настройки (SQLite, JWT)
│   │   ├── database.py       # Подключение к БД (aiosqlite)
│   │   └── main.py           # FastAPI приложение
│   ├── tests/                # pytest тесты (auth + masters CRUD)
│   ├── requirements.txt      # Зависимости Python
│   └── pyproject.toml        # Конфиг pytest
├── frontend/
│   ├── src/
│   │   ├── api/              # API клиент (axios)
│   │   ├── pages/            # React страницы (8 страниц: публичные + админ-панель)
│   │   ├── App.tsx           # Роутинг
│   │   └── main.tsx          # Точка входа
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml        # Docker-конфиг (PostgreSQL + Redis, для production)
├── start.bat                 # Запуск backend + frontend (Windows)
├── run_backend.bat           # Запуск backend только (Windows)
└── run_frontend.bat          # Запуск frontend только (Windows)
```

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

### Admin (JWT required)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/admin/dashboard` | Статистика (записи, клиенты, доход) |
| `GET` | `/admin/appointments` | Список записей |
| `PATCH` | `/admin/appointments/{id}/confirm` | Подтвердить запись |
| `PATCH` | `/admin/appointments/{id}/cancel` | Отменить запись |
| `POST` | `/admin/services` | Создать услугу |
| `PATCH` | `/admin/services/{id}` | Обновить услугу |
| `DELETE` | `/admin/services/{id}` | Удалить услугу |
| `GET` | `/admin/working-hours` | Расписание |
| `POST` | `/admin/working-hours` | Добавить рабочий день |
| `DELETE` | `/admin/working-hours/{id}` | Удалить рабочий день |
| `GET` | `/admin/appointments/by-date` | Записи по дате |

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

## 🧪 Тесты

```powershell
cd backend
$env:PYTHONPATH='.'
pytest tests/ -v                          # Все тесты
pytest tests/test_auth.py -v              # Только auth
pytest tests/test_masters.py -v           # Только masters
pytest tests/ -v --cov=app                # С покрытием
```

## 🗄️ База данных

**Локальная разработка:** SQLite (aiosqlite) — таблицы создаются автоматически при старте.

**Production:** PostgreSQL 16 (через Docker Compose).

## 📚 Документация

- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — архитектура системы
- [`SETUP.md`](./SETUP.md) — подробная настройка
- [`QUICK_START.md`](./QUICK_START.md) — быстрый старт и примеры API
- [`CHANGELOG.md`](./CHANGELOG.md) — история изменений

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

## 🔐 Админ-панель

Вход: `/admin/login` — используйте email и пароль зарегистрированного мастера.

Функции:
- **Дашборд** — статистика записей, клиентов, услуг, доход
- **Записи** — фильтрация по статусу, подтверждение, отмена
- **Услуги** — создание, редактирование, удаление
- **Расписание** — управление рабочими часами

## 📝 Лицензия

MIT

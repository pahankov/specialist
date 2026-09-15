# Sugar Booking — Система записи на шугаринг

Приложение для записи клиентов к мастеру шугаринга через веб-интерфейс.

## 🚀 Быстрый старт

### Требования

- **Python** 3.11+
- **Node.js** 20+
- **pip** (для управления зависимостями)

### Запуск

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
│   │   ├── api/              # REST endpoints (auth, masters, services, appointments, clients, working_hours)
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic schemas (request/response validation)
│   │   ├── config.py         # Настройки (SQLite, JWT)
│   │   ├── database.py       # Подключение к БД (aiosqlite)
│   │   └── main.py           # FastAPI приложение
│   ├── tests/                # pytest тесты
│   ├── requirements.txt      # Зависимости Python
│   └── pyproject.toml        # Конфиг pytest
├── frontend/
│   ├── src/
│   │   ├── api/              # API клиент (axios)
│   │   ├── pages/            # React страницы (HomePage, BookingPage)
│   │   ├── App.tsx           # Роутинг
│   │   └── main.tsx          # Точка входа
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml        # Docker-конфиг (PostgreSQL + Redis, для production)
├── run_backend.bat           # Батник для запуска backend (Windows)
└── run_frontend.bat          # Батник для запуска frontend (Windows)
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

### Clients
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/clients/` | Список клиентов |

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

## 📝 Лицензия

MIT

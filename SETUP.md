# Setup Instructions

## Environment Configuration

### Backend

Backend использует SQLite по умолчанию. База данных создаётся автоматически при первом запуске.

Файл `sugar_booking.db` находится в корне проекта. Для production используйте PostgreSQL через Docker Compose.

### Frontend

Переменные окружения фронтенда настраиваются в `frontend/vite.config.ts`:

```ts
server: {
  port: 3000,
  host: '0.0.0.0',
}
```

API URL задаётся в `frontend/src/api/client.ts`:

```ts
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
```

## Запуск

### Backend

```powershell
cd backend
$env:PYTHONPATH='.'
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd frontend
npm run dev
```

### Docker (production)

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## Доступные URL

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| API Docs (Swagger) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

## Инициализация БД

При первом запуске backend автоматически создаст все таблицы:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

## Тесты

```powershell
cd backend
$env:PYTHONPATH='.'
pytest tests/ -v                          # Все тесты
pytest tests/test_auth.py -v              # Только auth
pytest tests/ -v --cov=app                # С покрытием
```

## Структура базы данных

```
sugar_booking.db (SQLite)
├── masters           # Мастера
├── services          # Услуги
├── appointments      # Записи
├── clients           # Клиенты
├── working_hours     # Рабочее время
└── blocked_slots     # Заблокированные слоты
```

# Setup Instructions

## Environment Configuration

### Backend Configuration

Создайте файл `backend/config.env` с содержимым:

```
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/sugar_booking
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key-change-in-production
ACCESS_TOKEN_EXPIRE_MINUTES=10080
APP_NAME=Sugar Booking API
DEBUG=true
TELEGRAM_BOT_TOKEN=
VK_API_TOKEN=
MAX_API_TOKEN=
```

### Frontend Configuration

Переменные окружения фронтенда устанавливаются в `docker-compose.yml`:

```
VITE_API_URL=http://localhost:8000
```

## Docker Compose

```bash
# Запуск всех сервисов
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## Локальная разработка

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Доступные URL

- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend: http://localhost:3000

## Инициализация БД

При первом запуске backend автоматически создаст все таблицы благодаря:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

## Интеграция мессенджеров (позже)

- Telegram: Используйте `TELEGRAM_BOT_TOKEN`
- VK: Используйте `VK_API_TOKEN`
- MAX: Используйте `MAX_API_TOKEN`
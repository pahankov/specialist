# Sugar Booking - Appointment Booking System

Приложение для записи клиентов к мастеру шугаринга через мессенджеры (MAX, Telegram, VK).

## 🚀 Быстрый старт

### Требования
- Docker & Docker Compose
- Python 3.12+ (для локальной разработки без Docker)
- Node.js 20+ (для локальной разработки фронтенда)

### Установка и запуск

#### С Docker (рекомендуется)

```bash
cd sugar-booking
docker-compose up -d
```

Приложение будет доступно:
- **API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000

#### Локальная разработка

**Backend:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt

# Создайте config.env из примера
echo 'DATABASE_URL=postgresql://postgres:postgres@localhost:5432/sugar_booking' > config.env
echo 'REDIS_URL=redis://localhost:6379/0' >> config.env

# Запустите PostgreSQL и Redis (если не используется Docker)
uvicorn app.main:app --reload
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

## 📋 Структура проекта

```
sugar-booking/
├── backend/
│   ├── app/
│   │   ├── api/              # REST endpoints
│   │   ├── models/           # SQLAlchemy models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── workers/          # Background tasks
│   │   ├── config.py         # Settings
│   │   ├── database.py       # DB connection
│   │   └── main.py           # FastAPI app
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── pages/            # React pages
│   │   ├── components/       # React components
│   │   ├── api/              # API client
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

## 🔌 API Endpoints

### Masters
- `GET /api/v1/masters/` - Список мастеров
- `GET /api/v1/masters/{id}` - Мастер по ID
- `POST /api/v1/masters/` - Создать мастера
- `PATCH /api/v1/masters/{id}` - Обновить мастера
- `DELETE /api/v1/masters/{id}` - Удалить мастера

### Services
- `GET /api/v1/services/` - Список услуг
- `POST /api/v1/services/` - Создать услугу
- `PATCH /api/v1/services/{id}` - Обновить услугу
- `DELETE /api/v1/services/{id}` - Удалить услугу

### Appointments
- `GET /api/v1/appointments/` - Список записей
- `POST /api/v1/appointments/` - Создать запись
- `POST /api/v1/appointments/{id}/cancel` - Отменить запись

### Reviews
- `GET /api/v1/reviews/` - Список отзывов
- `POST /api/v1/reviews/` - Оставить отзыв
- `PATCH /api/v1/reviews/{id}` - Обновить отзыв

### Working Hours
- `GET /api/v1/working-hours/` - Рабочее расписание
- `POST /api/v1/working-hours/` - Добавить часы работы
- `DELETE /api/v1/working-hours/{id}` - Удалить часы

### Blocked Slots
- `GET /api/v1/blocked-slots/` - Заблокированные слоты
- `POST /api/v1/blocked-slots/` - Заблокировать время
- `DELETE /api/v1/blocked-slots/{id}` - Разблокировать время

## 🗄️ База данных

Схема включает таблицы:
- `masters` - мастера
- `services` - услуги
- `appointments` - записи
- `reviews` - отзывы
- `working_hours` - расписание
- `blocked_slots` - блокировки
- `notifications` - напоминания
- `chat_messages` - сообщения

## 📝 Следующие шаги

- [ ] Интеграция с Telegram Bot API
- [ ] Интеграция с VK API
- [ ] Интеграция с MAX API
- [ ] Система аутентификации мастера
- [ ] Админ-панель для мастера
- [ ] Система напоминаний и уведомлений
- [ ] Проверка доступности слотов
- [ ] Tests (unit & integration)
- [ ] CI/CD pipeline

## 🤝 Контрибьютинг

Любые улучшения приветствуются!

## 📄 Лицензия

MIT
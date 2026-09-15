# Quick Start Guide

## 🚀 Запуск проекта локально

### Windows

**Способ 1: Двойной клик на батники**

1. Откройте `sugar-booking/run_backend.bat` (откроется консоль с backend)
2. Откройте `sugar-booking/run_frontend.bat` (откроется консоль с frontend)
3. Подождите 10-15 секунд инициализации

**Способ 2: Вручную через PowerShell**

```powershell
# Terminal 1 - Backend
cd sugar-booking\backend
.\venv\Scripts\activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Frontend
cd sugar-booking\frontend
npm run dev
```

### macOS/Linux

```bash
# Terminal 1 - Backend
cd sugar-booking/backend
source venv/bin/activate
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Frontend
cd sugar-booking/frontend
npm run dev
```

---

## 📍 Доступные сервисы

После запуска откройте в браузере:

- **API Documentation**: http://localhost:8000/docs
- **Frontend (PWA)**: http://localhost:3000
- **Health Check**: http://localhost:8000/health

---

## 🧪 Тестирование API

### 1. Регистрация мастера

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Маша",
    "phone": "+79999999999",
    "telegram_username": "masha_sugar",
    "email": "masha@example.com",
    "password": "securepassword123"
  }'
```

### 2. Логин мастера

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login?email=masha@example.com&password=securepassword123"
```

Ответ:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "master": { ... }
}
```

### 3. Создание услуги

```bash
curl -X POST http://localhost:8000/api/v1/services/ \
  -H "Content-Type: application/json" \
  -d '{
    "master_id": 1,
    "name": "Шугаринг ног полностью",
    "duration_minutes": 60,
    "price": 2500.00
  }'
```

### 4. Создание рабочих часов

```bash
curl -X POST http://localhost:8000/api/v1/working-hours/ \
  -H "Content-Type: application/json" \
  -d '{
    "master_id": 1,
    "day_of_week": 0,
    "start_time": "10:00:00",
    "end_time": "20:00:00"
  }'
```

### 5. Получение доступных слотов (для клиента)

```bash
curl "http://localhost:8000/api/v1/appointments/available-slots?master_id=1&service_id=1&date=2026-09-10"
```

### 6. Создание записи клиентом

```bash
curl -X POST http://localhost:8000/api/v1/appointments/public \
  -H "Content-Type: application/json" \
  -d '{
    "master_id": 1,
    "service_id": 1,
    "client_name": "Иван",
    "client_phone": "+79991234567",
    "appointment_date": "2026-09-10T14:00:00"
  }'
```

### 7. Получение всех клиентов

```bash
curl http://localhost:8000/api/v1/clients/
```

---

## 🎯 Функциональность

### ✅ Реализовано

- ✅ Регистрация и аутентификация мастера (JWT)
- ✅ Управление услугами
- ✅ Управление рабочим расписанием
- ✅ Блокировка времени (отпуск, выходные)
- ✅ Расчёт доступных слотов
- ✅ Создание записей клиентами (с автоматическим созданием клиента)
- ✅ Управление клиентами
- ✅ Отзывы и комментарии
- ✅ PWA фронтенд для бронирования

### 🔄 В разработке

- 🔄 Админ-панель для мастера (календарь + управление записями)
- 🔄 Автоподтверждение записей (через 1 час)
- 🔄 Система уведомлений
- 🔄 Интеграция с мессенджерами (Telegram, VK, MAX)

### ⏳ Планируется

- ⏳ Редактирование записей мастером
- ⏳ Отправка уведомлений при изменении записи
- ⏳ История операций
- ⏳ Аналитика

---

## 📊 Структура БД

База автоматически создаётся при первом запуске backend:

```
sugar_booking.db (SQLite)
├── masters (мастера)
├── clients (клиенты)
├── services (услуги)
├── appointments (записи)
├── reviews (отзывы)
├── working_hours (рабочее время)
├── blocked_slots (блокировки)
├── notifications (уведомления)
└── chat_messages (сообщения)
```

---

## 🐛 Решение проблем

### Backend не запускается

```bash
cd sugar-booking/backend
.\venv\Scripts\pip install --upgrade -r requirements.txt
```

### Frontend не подгружается

```bash
cd sugar-booking/frontend
rm -rf node_modules
npm install
npm run dev
```

### Port 8000 / 3000 already in use

```bash
# Найти процесс на порту 8000
netstat -ano | findstr :8000

# Убить процесс (Windows)
taskkill /PID <PID> /F
```

---

## 📚 Документация

См. также:
- `README.md` — обзор проекта
- `ARCHITECTURE.md` — архитектура системы
- `API_EXAMPLES.md` — примеры API
- `PROJECT_STATUS.md` — статус разработки

---

**Версия**: 0.2.0 (с аутентификацией и логикой доступных слотов)  
**Последнее обновление**: 2026-09-09
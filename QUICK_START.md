# Quick Start Guide

## 🚀 Запуск проекта локально

### Backend (Windows PowerShell)

```powershell
cd backend
$env:PYTHONPATH='.'
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend (Windows PowerShell)

```powershell
cd frontend
npm run dev
```

### Батники (Windows)

```
run_backend.bat    # Запуск backend
run_frontend.bat   # Запуск frontend
```

## 📍 Доступные сервисы

| Сервис | URL |
|--------|-----|
| Frontend | http://localhost:3000 |
| API Docs (Swagger UI) | http://localhost:8000/docs |
| Health Check | http://localhost:8000/health |

## 🧪 Тестирование API

### 1. Регистрация мастера

```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Елена",
    "email": "elena@example.com",
    "password": "SecurePass123!",
    "phone": "+79991234567",
    "telegram_username": "elena_sugar"
  }'
```

Ответ:
```json
{
  "id": 1,
  "name": "Елена",
  "email": "elena@example.com",
  "phone": "+79991234567",
  "telegram_username": "elena_sugar"
}
```

### 2. Логин мастера

```bash
curl -X POST "http://localhost:8000/api/v1/auth/login?email=elena@example.com&password=SecurePass123!"
```

Ответ:
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer"
}
```

### 3. Создание услуги

```bash
curl -X POST http://localhost:8000/api/v1/services/ \
  -H "Content-Type: application/json" \
  -d '{
    "master_id": 1,
    "name": "Шугаринг ног полностью",
    "description": "Удаление волос на ногах сахарной пастой",
    "duration_minutes": 60,
    "price": 2500
  }'
```

### 4. Создание записи клиентом

```bash
curl -X POST http://localhost:8000/api/v1/appointments/public \
  -H "Content-Type: application/json" \
  -d '{
    "master_id": 1,
    "service_id": 1,
    "client_name": "Иван",
    "client_phone": "+79991234567",
    "appointment_date": "2026-09-20T14:00:00"
  }'
```

### 5. Получение доступных слотов

```bash
curl "http://localhost:8000/api/v1/appointments/available-slots?master_id=1&service_id=1&date=2026-09-20"
```

### 6. Получение списка мастеров

```bash
curl http://localhost:8000/api/v1/masters/
```

### 7. Обновление мастера

```bash
curl -X PATCH http://localhost:8000/api/v1/masters/1 \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Елена Иванова",
    "phone": "+79999999999"
  }'
```

### 8. Удаление мастера

```bash
curl -X DELETE http://localhost:8000/api/v1/masters/1
```

## 🎯 Что реализовано

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
- Адаптивный дизайн

### ✅ Тесты
- 18 pytest-тестов (auth + masters CRUD)
- In-memory SQLite для изоляции тестов
- pytest-asyncio для асинхронных тестов

## 🐛 Решение проблем

### Backend не запускается

```powershell
cd backend
pip install -r requirements.txt
pip install pytest httpx pytest-asyncio pytest-cov
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

## 🧪 Запуск тестов

```powershell
cd backend
$env:PYTHONPATH='.'
pytest tests/ -v                          # Все тесты
pytest tests/test_auth.py -v              # Только auth
pytest tests/test_masters.py -v           # Только masters
pytest tests/ -v --cov=app                # С покрытием
```

## 📚 Документация

- [`README.md`](./README.md) — обзор проекта
- [`ARCHITECTURE.md`](./ARCHITECTURE.md) — архитектура системы
- [`SETUP.md`](./SETUP.md) — подробная настройка
- [`CHANGELOG.md`](./CHANGELOG.md) — история изменений

---

**Версия**: 0.3.0  
**Последнее обновление**: 2026-09-15

# Changelog

## [0.2.0] - 2026-09-09

### ✨ Added (Добавлено)

#### Backend
- **Аутентификация мастера**
  - Регистрация мастера с email/password
  - Логин с выдачей JWT токена
  - Защита приватных роутов через Bearer token
  - Хеширование паролей (bcrypt)

- **Управление клиентами**
  - Таблица clients (name, phone, email)
  - Автоматическое создание клиента при бронировании
  - API для поиска и управления клиентами

- **Логика доступных слотов** (SlotService)
  - Расчёт свободных 30-минутных слотов
  - Учёт рабочих часов мастера
  - Исключение заблокированного времени
  - Исключение существующих записей
  - API эндпоинты: `/available-slots` и `/available-days`

- **Обновлённая модель Appointment**
  - Связь с Client (client_id)
  - Статусы: pending, confirmed, cancelled, completed
  - Поле confirmed_at (когда мастер подтвердил)
  - Поле notes (заметки мастера)

- **API эндпоинты**
  - `POST /api/v1/auth/register` — регистрация мастера
  - `POST /api/v1/auth/login` — логин
  - `GET /api/v1/auth/me` — получить информацию текущего мастера
  - `GET /api/v1/clients/` — список клиентов
  - `POST /api/v1/clients/` — создать клиента
  - `GET /api/v1/appointments/available-days` — доступные дни
  - `GET /api/v1/appointments/available-slots` — доступные слоты
  - `POST /api/v1/appointments/public` — создать запись (для клиента)

#### Frontend
- Обновлённый API клиент с поддержкой новых эндпоинтов
- Типизация для Client и обновлённого Appointment
- Базовая структура для админ-панели (готовая к реализации)

#### Utilities
- `utils.py` — функции для работы с паролями и JWT токенами
- SlotService — сервис для расчёта доступных слотов

### 🔄 Changed (Изменено)

- Обновлена модель Appointment (добавлена связь с Client)
- Обновлена модель Review (добавлена связь с Client)
- Обновлена модель Master (email и hashed_password теперь обязательны)
- Конфигурация использует SQLite для локальной разработки (вместо PostgreSQL)
- Все роутеры обновлены на синхронную работу с Session (вместо AsyncSession)

### 📚 Documentation
- Добавлен `QUICK_START.md` — быстрый старт
- Добавлен `CHANGELOG.md` (этот файл)
- Обновлён `README.md` со ссылками на новые страницы

### 🔧 Infrastructure
- Созданы батники для запуска: `run_backend.bat`, `run_frontend.bat`
- Обновлены инструкции по локальному запуску без Docker

---

## [0.1.0] - 2026-09-09 (Initial)

### ✨ Added
- Полная архитектура проекта (backend + frontend)
- 8 моделей данных (Master, Service, Appointment, Review, WorkingHour, BlockedSlot, Notification, ChatMessage)
- 6 API роутеров (masters, services, appointments, reviews, working_hours, blocked_slots)
- React + TypeScript фронтенд с PWA поддержкой
- Docker Compose конфигурация
- Полная документация проекта

---

## 🚀 Следующие шаги (v0.3.0)

1. **Админ-панель для мастера**
   - Страница `/admin` с защитой JWT
   - Календарь с визуализацией записей и блокировок
   - Список клиентов с фильтрацией
   - Управление услугами
   - Редактирование/удаление записей

2. **Автоподтверждение записей**
   - Background worker для проверки pending записей
   - Автоматическое подтверждение через 1 час
   - Уведомление клиента при подтверждении

3. **Система уведомлений**
   - Отправка напоминаний (24ч, 1ч до записи)
   - Уведомление при изменении записи
   - Поддержка разных каналов (пока заглушки)

4. **Интеграция с мессенджерами**
   - Telegram Bot API
   - VK API
   - MAX API
   - DeepLink для открытия PWA из мессенджеров

---

## 📊 Статистика кода

| Компонент | Строк кода | Файлов |
|-----------|-----------|--------|
| Backend моделей | ~150 | 9 |
| Backend схем | ~300 | 9 |
| Backend роутеров | ~450 | 7 |
| Backend сервисов | ~200 | 2 |
| Backend утилит | ~80 | 1 |
| Frontend компонентов | ~350 | 5 |
| Frontend API | ~100 | 2 |
| Frontend стилей | ~300 | 4 |
| **Итого** | **~1930** | **39** |

---

## 🙏 Благодарности

Архитектура и best practices основаны на:
- FastAPI official documentation
- SQLAlchemy async patterns
- React 18 patterns
- JWT authentication standards
- PostgreSQL & SQLite design patterns
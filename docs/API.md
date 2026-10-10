# API Reference — Online Booking

> Таблицы эндпоинтов и curl-кукбук. Вынесено из README для компактности.
> Base URL (local): `http://localhost:8000`. Интерактивная документация: `/docs`.

## 🔌 API Endpoints

### Auth
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/register` | Регистрация мастера (с выбором города) |
| `POST` | `/api/v1/auth/login` | Вход мастера (JWT + refresh token в cookies) |
| `POST` | `/api/v1/auth/login-unified` | Вход по email ИЛИ телефону (мастера и клиенты; пишет login в аудит) |
| `POST` | `/api/v1/auth/register-unified` | Регистрация с выбором роли |
| `POST` | `/api/v1/auth/send-otp` | Отправка SMS-кода клиенту |
| `POST` | `/api/v1/auth/verify-otp` | Проверка кода, вход/регистрация клиента |
| `POST` | `/api/v1/auth/refresh` | Обновление access token (refresh token rotation) |
| `POST` | `/api/v1/auth/logout` | Выход (очистка cookies) |
| `POST` | `/api/v1/auth/client/login` | Legacy вход клиента по телефону |

### MAX chat-bot auth (SMS-style; бот @se14458556_bot)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/max/start` | Заявка на код (код НЕ возвращается — бот пришлёт его в диалог; 10/min) |
| `POST` | `/api/v1/auth/max/verify` | Проверка кода с сайта, JWT-сессия + cookies (10/min) |
| `POST` | `/api/max/webhook` | Приём MAX Bot API updates (`message_created`, `bot_started`; секрет `X-Max-Bot-Api-Secret`) |

Флоу: сайт берёт телефон → юзер делится номером с ботом (текст или кнопка
`request_contact`) → бот присылает код в диалог (+ кнопка «Скопировать код») →
юзер вводит код на сайте. Номер из `request_contact` с верным HMAC — доказанно
привязан к MAX-аккаунту (`is_verified=True`); набранный текстом — нет
(`is_verified=False`, как в SMS-флоу). Имя из MAX — дефолт нового клиента.

### Geography
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/countries/` | Список стран |
| `GET` | `/api/v1/cities/` | Список городов (пагинация, поиск, фильтр по стране) |
| `GET` | `/api/v1/cities/search/?q=&limit=` | Поиск городов для автокомплита (фолбэк DaData) |
| `GET` | `/api/v1/cities/{id}` | Город по ID |
| `POST` | `/api/v1/cities/resolve` | Get-or-create города по точному имени (выбор из DaData; master+) |

### DaData (backend proxy, секрет не покидает сервер)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/dadata/{path}` | Прокси в DaData 4_1/rs: форвардит тело, зеркалит статус (503 — нет ключей, 502 — апстрим недоступен) |

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
| `POST` | `/admin/appointments/book` | Админская запись (выбор клиента из БД; суперадмин шлёт `master_id`) |
| `GET` | `/admin/appointments/by-date` | Записи по дате |
| `PATCH` | `/admin/appointments/{id}/confirm` | Подтвердить запись |
| `PATCH` | `/admin/appointments/{id}/cancel` | Отменить запись |
| `PATCH` | `/admin/appointments/{id}/complete` | Завершить запись |
| `DELETE` | `/admin/appointments/{id}` | Удалить запись |
| `GET` | `/admin/services` | Список активных услуг |
| `GET` | `/admin/services/all` | Все услуги (включая неактивные; суперадмин: `?master_id=`) |
| `POST` | `/admin/services` | Создать услугу |
| `PATCH` | `/admin/services/{id}` | Обновить услугу |
| `DELETE` | `/admin/services/{id}` | Soft-delete услуги |
| `GET` | `/admin/clients` | Список клиентов (пагинация; есть `city_id`/`city_name`) |
| `POST` | `/admin/clients` | Создать клиента (можно с `city_id`) |
| `PATCH` | `/admin/clients/{id}` | Обновить клиента (можно `city_id`) |
| `DELETE` | `/admin/clients/{id}` | Удалить клиента |
| `POST` | `/admin/clients/bulk-city` | Назначить город всем по фильтру (`city_id` + `search`/`master_id`) |
| `GET` | `/admin/working-hours` | Расписание |
| `POST` | `/admin/working-hours` | Добавить рабочий день |
| `PATCH` | `/admin/working-hours/{id}` | Обновить рабочий день |
| `DELETE` | `/admin/working-hours/{id}` | Удалить рабочий день |
| `GET` | `/admin/work-window` | Окно рабочего времени мастера (`?master_id=` для суперадмина) |
| `PATCH` | `/admin/work-window` | Задать окно (`start_hour`/`end_hour`, 0–24) |
| `GET` | `/admin/audit-logs` | Журнал действий (пагинация, фильтрация; есть сущность `auth` — входы/выходы) |
| `GET` | `/admin/export/appointments` | Экспорт записей в CSV (`status`, `master_id`, `ids`, `include_master`) |
| `GET` | `/admin/export/clients` | Экспорт клиентов в CSV (`ids`, `search`, `master_id`; есть колонка Город) |
| `GET` | `/admin/export/masters` | Экспорт мастеров в CSV (суперадмин; `ids`) |
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
| `POST` | `/admin/masters/{id}/toggle-active` | Блокировка/разблокировка мастера (оба флага + аудит) |
| `POST` | `/admin/masters/{id}/toggle-admin` | Выдать/снять права суперадмина |
| `GET` | `/admin/masters/{id}/full` | Полная карточка (статистика, рейтинг, отзывы, записи) |
| `POST` | `/admin/masters/{id}/suspend` | Заблокировать навсегда |
| `POST` | `/admin/masters/{id}/unsuspend` | Разблокировать |
| `POST` | `/admin/masters/{id}/refresh-status` | Пересчитать статус по рабочим часам |
| `GET` | `/admin/masters/{id}/stats` | Статистика по мастеру |
| `POST` | `/admin/masters/bulk/toggle-active` | Массовая смена статуса |
| `POST` | `/admin/masters/bulk/suspend` | Массовая блокировка |
| `POST` | `/admin/masters/bulk/unsuspend` | Массовая разблокировка |
| `POST` | `/admin/masters/import` | Импорт мастеров из CSV |
| `POST` | `/admin/masters/{id}/impersonate` | Вход от имени мастера (support view-as, пишется в аудит) |
| `PATCH` | `/admin/masters/{id}/password` | Сброс пароля мастера (+ отзыв сессий) |
| `GET` | `/admin/masters/{id}/sessions` | Активные сессии (без значений токенов) |
| `DELETE` | `/admin/masters/{id}/sessions` | Отозвать все сессии мастера |
| `GET` | `/admin/reviews` | Все отзывы (пагинация, фильтры: master_id, is_published) |
| `GET` | `/admin/reviews/average/{master_id}` | Средний рейтинг мастера |
| `PATCH` | `/admin/reviews/{id}/publish` | Опубликовать отзыв |
| `PATCH` | `/admin/reviews/{id}/unpublish` | Скрыть отзыв |
| `DELETE` | `/admin/reviews/{id}` | Удалить отзыв |
| `GET` | `/admin/audit-logs?master_id=X` | Логи действий (фильтр по мастеру) |
| `GET` | `/admin/global-stats` | Глобальная статистика по всей системе |
| `POST` | `/admin/dashboard/cache/clear` | Сброс кэша дашборда |

### Health & Changelog
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/health` | Быстрая проверка (без БД) |
| `GET` | `/admin/health` | Полная проверка (DB + Redis cache + RQ) |
| `GET` | `/admin/health/verbose` | Расширенная (метрики БД, статистика RQ) |
| `GET` | `/admin/changelog` | История версий API |

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

## 🌱 Seed-скрипт
```powershell
cd backend
$env:PYTHONPATH='.'
python create_superuser.py
# Создаёт суперпользователя с ролью ADMIN
```

### Логин мастера (возвращает cookies)
```bash
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"elena@example.com","password":"SecurePass123!"}'
```

### OTP: отправка кода клиенту
```bash
curl -X POST http://localhost:8000/api/v1/auth/send-otp \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79991234567"}'
```

### OTP: проверка кода
```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"phone":"+79991234567","code":"A1B2C3"}'
```

### Обновление токена
```bash
curl -X POST http://localhost:8000/api/v1/auth/refresh
```

### Выход (очистка cookies)
```bash
curl -X POST http://localhost:8000/api/v1/auth/logout
```

### Список городов
```bash
curl -X GET "http://localhost:8000/api/v1/cities/?country_id=1&page=1&page_size=50"
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

### Health check
```bash
# Быстрая проверка
curl -X GET http://localhost:8000/health

# Полная проверка (DB + Redis + RQ)
curl -X GET http://localhost:8000/api/v1/admin/health

# Расширенная (с метриками)
curl -X GET http://localhost:8000/api/v1/admin/health/verbose
```

### API Changelog
```bash
# История версий API
curl -X GET http://localhost:8000/api/v1/admin/changelog
```

### Admin reviews
```bash
# Список всех отзывов (пагинация)
curl -X GET "http://localhost:8000/api/v1/admin/reviews?page=1&page_size=20"

# Фильтр по мастеру
curl -X GET "http://localhost:8000/api/v1/admin/reviews?master_id=1&is_published=true"

# Опубликовать отзыв
curl -X PATCH http://localhost:8000/api/v1/admin/reviews/1/publish \
  -H "Authorization: Bearer <token>"

# Скрыть отзыв
curl -X PATCH http://localhost:8000/api/v1/admin/reviews/1/unpublish \
  -H "Authorization: Bearer <token>"

# Удалить отзыв
curl -X DELETE http://localhost:8000/api/v1/admin/reviews/1 \
  -H "Authorization: Bearer <token>"

# Средний рейтинг мастера
curl -X GET "http://localhost:8000/api/v1/admin/reviews/average/1"
```

### Master detail (full profile)
```bash
# Полная карточка мастера (статистика, рейтинг, отзывы, записи)
curl -X GET http://localhost:8000/api/v1/admin/masters/1/full \
  -H "Authorization: Bearer <token>"
```

### Bulk operations
```bash
# Массовая смена статуса
curl -X POST http://localhost:8000/api/v1/admin/masters/bulk/toggle-active \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '[1, 2, 3]'

# Массовая блокировка
curl -X POST http://localhost:8000/api/v1/admin/masters/bulk/suspend \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '[1, 2, 3]'
```

### Master import from CSV
```bash
# Импорт мастеров из CSV (name,email,password,phone,telegram_username)
curl -X POST http://localhost:8000/api/v1/admin/masters/import \
  -H "Authorization: Bearer <token>" \
  -F "file=@masters.csv"
```

### Background export
```bash
# Запуск фонового экспорта
curl -X POST "http://localhost:8000/api/v1/admin/export/appointments?background=true&status=pending" \
  -H "Authorization: Bearer <token>"

# Статус задачи
curl -X GET http://localhost:8000/api/v1/admin/export/appointments/status/<job_id> \
  -H "Authorization: Bearer <token>"

# Статистика очереди задач
curl -X GET http://localhost:8000/api/v1/admin/export/stats \
  -H "Authorization: Bearer <token>"
```

### Audit logs by master
```bash
# Логи действий по конкретному мастеру
curl -X GET "http://localhost:8000/api/v1/admin/audit-logs?master_id=1&page=1&page_size=20" \
  -H "Authorization: Bearer <token>"
```

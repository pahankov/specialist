# Тестирование Backend API

## 📋 Содержание

- [Структура тестов](#структура-тестов)
- [Запуск тестов](#запуск-тестов)
- [Архитектура тестов](#архитектура-тестов)
- [Критические правила](#критические-правила)
- [Известные проблемы и решения](#известные-проблемы-и-решения)
- [Написание новых тестов](#написание-новых-тестов)

---

## Структура тестов

```
tests/
├── conftest.py                    # Общие фикстуры (engine, session, client)
├── test_admin_appointments.py     # CRUD записей (16 тестов, все PASS)
├── test_admin_clients.py          # CRUD клиентов (11 тестов, все PASS)
├── test_admin_services.py         # CRUD услуг (9 тестов, все PASS)
├── test_admin_audit.py            # Аудит-логи (4 теста)
├── test_admin_dashboard.py        # Дашборд (4 теста)
├── test_admin_working_hours.py    # Рабочие часы (10 тестов)
├── test_appointments.py           # Записи (7 тестов)
├── test_auth.py                   # Регистрация/логин (8 тестов)
├── test_auth_tokens.py            # JWT токены (12 тестов, все PASS)
├── test_auth_dependencies.py      # Auth dependencies (10 тестов)
├── test_auth_service.py           # Auth service (12 тестов)
├── test_cache_service.py          # Redis cache (18 тестов, все PASS)
├── test_clients.py                # Клиенты (8 тестов)
├── test_masters.py                # Мастера (10 тестов)
├── test_masters_bulk.py           # Массовые операции (6 тестов)
├── test_masters_crud.py           # CRUD мастеров (17 тестов)
├── test_masters_status.py         # Управление статусом (11 тестов)
├── test_password_security.py      # Безопасность паролей (9 тестов)
├── test_rate_limiting.py          # Rate limiting (9 тестов)
├── test_refresh_tokens.py         # Refresh токены (6 тестов)
├── test_reviews.py                # Отзывы (10 тестов)
├── test_services.py               # Услуги (7 тестов)
└── ...                            # Остальные тесты
```

---

## Запуск тестов

```powershell
# Все тесты
cd online-booking\backend
$env:PYTHONPATH='.'
pytest tests/ -v

# Конкретный файл
pytest tests/test_masters_crud.py -v

# Конкретный тест
pytest tests/test_masters_crud.py::TestGetMasters::test_list_masters_empty -v

# С покрытием
pytest tests/ -v --cov=app --cov-report=html

# Только passed/failed summary
pytest tests/ -v --tb=no
```

---

## Архитектура тестов

### Фикстуры (conftest.py)

#### `engine` — движок БД
- Создаётся **уникальный SQLite файл** для каждого теста (scope=function)
- Файл удаляется после теста
- Таблицы создаются через `Base.metadata.create_all`

#### `session` — сессия БД
```python
@pytest.fixture(scope="function")
async def session(engine) -> AsyncSession:
    """Create a new session — commits changes for test visibility."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s
        await s.commit()  # Commit so data is visible within the test
```

**Важно:** Используется `commit()`, а не `rollback()`. Это позволяет данным быть видимыми внутри теста между разными операциями.

#### `client` — HTTP клиент
- Переопределяет `get_db` на тестовую сессию
- Создаёт `httpx.AsyncClient` с `ASGITransport`

#### Helper фикстуры
- `test_master_data` — данные для регистрации мастера (включая `role: "MASTER"`)
- `created_master_id` — создаёт мастера напрямую в БД (через flush)
- `super_admin_user` — создаёт админа напрямую в БД
- `super_admin_headers` — JWT headers для админа

---

## Критические правила

### 1. ✅ Всегда используйте `await db.flush()` перед созданием связанных объектов

**Плохо:**
```python
new_user = User(...)
db.add(new_user)

# ❌ new_user.id == None!
master_profile = MasterProfile(user_id=new_user.id)  # user_id=None → IntegrityError
db.add(master_profile)
```

**Хорошо:**
```python
new_user = User(...)
db.add(new_user)
await db.flush()  # ✅ Получаем ID

# Теперь new_user.id доступен
master_profile = MasterProfile(user_id=new_user.id)
db.add(master_profile)
```

**Почему:** SQLAlchemy не назначает ID до flush/commit. Если создать связанную запись до flush, FK будет `None`.

---

### 2. ✅ Всегда указывайте `role` в тестовых данных

**Плохо:**
```python
test_master_data = {
    "name": "Test Master",
    "email": "test@example.com",
    "password": "SecurePass123!",
    # ❌ role не указан → 422 Unprocessable Entity
}
```

**Хорошо:**
```python
test_master_data = {
    "name": "Test Master",
    "email": "test@example.com",
    "password": "SecurePass123!",
    "role": "MASTER",  # ✅ Обязательно
}
```

**Почему:** `UserCreate` schema требует поле `role: UserRole`. Без него API возвращает 422.

---

### 3. ✅ Создавайте пользователей напрямую в БД для fixtures

**Плохо (через API):**
```python
@pytest.fixture
async def created_master_id(client, test_master_data):
    resp = await client.post("/api/v1/auth/register", json=test_master_data)
    return resp.json()["id"]  # ❌ Данные теряются из-за commit() в session fixture
```

**Хорошо (прямое создание):**
```python
@pytest.fixture
async def created_master_id(session, test_master_data):
    user = User(
        name=test_master_data["name"],
        email=test_master_data["email"],
        hashed_password=hash_password(test_master_data["password"]),
        phone=test_master_data["phone"],
        role=UserRole.MASTER,
        is_verified=True,
    )
    session.add(user)
    await session.flush()  # ✅ Получаем ID
    await session.refresh(user)
    return user.id
```

**Почему:** `session` fixture делает `commit()` после yield, а не `rollback()`. Данные создаются в той же сессии и видны в тесте.

---

### 4. ✅ Используйте class-based структуру для тестов

```python
class TestGetMasters:
    """Tests for GET /api/v1/admin/masters"""

    async def test_list_masters_empty(self, client, super_admin_headers):
        """Returns empty list when no masters exist."""
        resp = await client.get("/api/v1/admin/masters", headers=super_admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []
```

**Почему:** Лучше группировка, понятнее структура, легче находить падающие тесты.

---

### 5. ✅ Используйте правильные пути к API

**Правильные пути:**
- `/api/v1/admin/masters` — список всех мастеров (superadmin)
- `/api/v1/admin/masters/{id}` — мастер по ID
- `/api/v1/admin/{id}/toggle-active` — toggle статуса (без `/masters/`)
- `/api/v1/admin/masters/bulk/toggle-active` — bulk операции

**Неправильные пути:**
- ❌ `/api/v1/admin/masters/{id}/toggle-active` (нет `/masters/` в пути)
- ❌ `/api/v1/admin/masters/bulk` (нужно `/bulk/toggle-active`)

---

### 6. ✅ Телефон форматируется автоматически

API автоматически форматирует телефоны в `+7 (XXX) XXX-XX-XX`.

**Плохо:**
```python
# ❌ Поиск по неформатированному номеру
{"phone": "+79990001122"}  # В БД хранится как "+7 (999) 000-11-22"
```

**Хорошо:**
```python
# ✅ API сам форматировал при регистрации
# Или используйте отформатированный номер
{"phone": "+7 (999) 000-11-22"}
```

---

### 7. ✅ Проверяй формат ответа API: пагинация vs список

Некоторые endpoints возвращают **пагинированный ответ**, а не просто список.

**Пагинированный формат:**
```json
{
  "items": [...],
  "total": 5,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

**Плохо:**
```python
resp = await client.get("/api/v1/admin/appointments", headers=headers)
assert resp.json() == []  # ❌ Ошибка! Возвращается {'items': [], ...}
```

**Хорошо:**
```python
resp = await client.get("/api/v1/admin/appointments", headers=headers)
data = resp.json()
assert data["items"] == []
assert data["total"] == 0
```

**Endpoints с пагинацией:**
- `GET /api/v1/admin/appointments`
- `GET /api/v1/admin/clients`
- `GET /api/v1/admin/services`
- `GET /api/v1/admin/masters`

**Endpoints БЕЗ пагинации (возвращают список):**
- `GET /api/v1/admin/services/all`
- `POST /api/v1/services/` (возвращает один объект)

**Как проверить:** Всегда смотри router.py — если response_model=`PaginatedResponse[T]`, значит нужна обёртка `["items"]`.

---

### 8. ✅ При удалении связанных объектов — удаляй их правильно

**Плохо:**
```python
# ❌ Удаляем User, но ClientProfile остаётся с user_id=NULL
await db.delete(user)
await db.commit()
# → IntegrityError: NOT NULL constraint failed: client_profiles.user_id
```

**Хорошо:**
```python
# Сначала удаляем зависимые записи
profile = await db.execute(select(ClientProfile).where(ClientProfile.user_id == user_id))
if profile:
    await db.delete(profile.scalar())

# Потом удаляем пользователя
await db.delete(user)
await db.commit()
```

**Почему:** ForeignKey имеет `nullable=False`. Нужно удалить Child перед Parent.

---

### 9. ✅ При запросе ClientProfile по appointment.client_id — ищи по user_id

**Плохо:**
```python
# ❌ appointment.client_id — это user.id, а не client_profile.id
client = await db.execute(
    select(ClientProfile).where(ClientProfile.id == appointment.client_id)
)
# → Ничего не найдено!
```

**Хорошо:**
```python
# ✅ appointment.client_id — это user.id
client = await db.execute(
    select(ClientProfile).where(ClientProfile.user_id == appointment.client_id)
)
```

**Почему:** В Appointment.client_id хранится ID пользователя (user.id), а не ID профиля.

---

### 10. ✅ Импортируй все необходимые ORM-функции

**Плохо:**
```python
from sqlalchemy.orm import aliased, selectinload
# ...
select(User).options(joinedload(User.client_profile))  # ❌ NameError: joinedload not defined
```

**Хорошо:**
```python
from sqlalchemy.orm import aliased, selectinload, joinedload
# ...
select(User).options(joinedload(User.client_profile))  # ✅
```

**Почему:** `joinedload`, `selectinload`, `subqueryload` — это отдельные импорты, а не части одного модуля.

---

## Известные проблемы и решения

### Проблема 1: UNIQUE constraint failed

**Симптом:**
```
sqlite3.IntegrityError: UNIQUE constraint failed: users.phone
```

**Причина:** Фикстуры с фиксированными phone/email конфликтуют между тестами.

**Решение:**
1. Фикстуры создают пользователей напрямую в БД через `session`
2. `session` fixture делает `commit()` после теста, но данные видны внутри теста
3. Уникальные данные для каждого теста (уникальные email/phone)

---

### Проблема 2: NOT NULL constraint failed: master_profiles.user_id

**Симптом:**
```
sqlite3.IntegrityError: NOT NULL constraint failed: master_profiles.user_id
```

**Причина:** `new_user.id` равен `None` до `flush()`.

**Решение:** Добавить `await db.flush()` перед созданием `MasterProfile`.

**Где исправлено:** `app/modules/auth/service.py` — функция `register_master`

---

### Проблема 3: 422 Unprocessable Entity при регистрации

**Симптом:**
```json
{
  "detail": [
    {
      "type": "missing",
      "loc": ["body", "role"],
      "msg": "Field required"
    }
  ]
}
```

**Причина:** Поле `role` обязательно в `UserCreate` schema.

**Решение:** Всегда включать `"role": "MASTER"` в тестовые данные.

---

### Проблема 4: 404 Not Found после создания записи

**Симптом:**
```python
resp = await client.post("/api/v1/admin/masters", json=data)
assert resp.status_code == 201

# Следующий запрос возвращает 404
resp2 = await client.get(f"/api/v1/admin/masters/{id}")
assert resp2.status_code == 200  # ❌ 404
```

**Причина:** `rollback()` в session fixture откатывает изменения.

**Решение:** Использовать `commit()` вместо `rollback()` в session fixture.

---

## Актуальная статистика

| Статус | Количество |
|--------|-----------|
| ✅ PASSED | 189 |
| ❌ FAILED | 28 |
| ⚠️ ERROR | 9 |
| **Всего** | **225** |

**Покрытие:** ~225 тестов, ~18000+ строк тестового кода, ~20 test files.

### Пройденные файлы (100% PASS):
- `test_admin_appointments.py` — 16/16 ✅
- `test_admin_clients.py` — 11/11 ✅
- `test_admin_services.py` — 9/9 ✅
- `test_auth_tokens.py` — 12/12 ✅
- `test_auth_service.py` — 12/12 ✅
- `test_cache_service.py` — 18/18 ✅
- `test_masters_crud.py` — 17/17 ✅
- `test_masters.py` — 10/10 ✅
- `test_rate_limiting.py` — 9/9 ✅

### Исправленные production-баги:
1. `_find_or_create_client` — добавлен `flush` перед созданием ClientProfile
2. `mark_no_show` — исправлен запрос: `ClientProfile.user_id` вместо `ClientProfile.id`
3. `delete_admin_client` — добавлено удаление ClientProfile перед User
4. `book_appointment` — добавлен импорт `joinedload`

---

## Написание новых тестов

### Шаг 1: Определите тип теста

- **Integration test** — тестирует endpoint через HTTP (использует `client`)
- **Unit test** — тестирует функцию/класс напрямую (использует `session` или ничего)

### Шаг 2: Выберите фикстуры

**Для integration tests:**
```python
async def test_something(self, client, super_admin_headers):
    """Нужен HTTP клиент и авторизация."""
    resp = await client.get("/api/v1/admin/masters", headers=super_admin_headers)
    assert resp.status_code == 200
```

**Для unit tests:**
```python
async def test_something(self, session):
    """Нужен доступ к БД напрямую."""
    user = User(...)
    session.add(user)
    await session.flush()
    # ...
```

### Шаг 3: Напишите тест

```python
class TestGetMasters:
    """Tests for GET /api/v1/admin/masters"""

    async def test_list_masters_empty(self, client, super_admin_headers):
        """Returns empty list when no masters exist."""
        resp = await client.get("/api/v1/admin/masters", headers=super_admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_masters_with_data(self, client, super_admin_headers, created_master_id):
        """Returns list of masters after registration."""
        resp = await client.get("/api/v1/admin/masters", headers=super_admin_headers)
        assert resp.status_code == 200
        masters = resp.json()
        assert len(masters) >= 1
        assert "id" in masters[0]
```

### Шаг 4: Запустите тест

```powershell
pytest tests/test_masters_crud.py::TestGetMasters::test_list_masters_empty -v
```

### Шаг 5: Проверьте результат

- ✅ **PASSED** — тест прошёл
- ❌ **FAILED** — проверьте traceback
- ⚠️ **ERROR** — проблема с фикстурой или импортом

---

## Чек-лист перед коммитом тестов

- [ ] Все тесты проходят (`pytest tests/ -v --tb=no`)
- [ ] Нет `ERROR` в результатах (только `PASSED` или `FAILED`)
- [ ] Фикстуры используют `flush()` перед созданием связанных объектов
- [ ] Тестовые данные включают `role` поле
- [ ] Используется class-based структура для группировки
- [ ] Путь к API правильный (проверьте router.py)
- [ ] Телефон отформатирован правильно (если нужно)
- [ ] Нет хардкода ID (используйте фикстуры)

---

## Полезные команды

```powershell
# Посмотреть только failing тесты
pytest tests/ -v --tb=short -x 2>&1 | Select-String "FAILED"

# Посмотреть только errors
pytest tests/ -v --tb=short -x 2>&1 | Select-String "ERROR"

# Запустить с подробным логом
pytest tests/ -v --log-cli-level=DEBUG

# Посчитать статистику
pytest tests/ -v --tb=no 2>&1 | Select-String "passed|failed|error"
```

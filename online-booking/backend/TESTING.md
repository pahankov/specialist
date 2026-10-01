# Тестирование Backend API

## 📋 Содержание

- [Структура тестов](#структура-тестов)
- [Запуск тестов](#запуск-тестов)
- [CI/CD и деплой](#cicd-и-деплой)
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

> ⚠️ **Этот раздел — источник истины.** Перед написанием любого теста прочитайте его полностью. 90% проблем при тестировании можно предотвратить, следуя этим правилам.

### 0. 🔴 КРИТИЧНО: Предотвращение ошибок (Checklist before every test)

**ПЕРЕД написанием теста задайте себе 5 вопросов:**

| # | Вопрос | Где проверить |
|---|--------|---------------|
| 1 | Нужен ли `role` в тестовых данных? | `schemas/user.py` → `UserCreate` |
| 2 | Нужен ли `flush()` перед созданием связанных объектов? | Модель имеет FK? → да, нужен `flush()` |
| 3 | Какой формат ответа: пагинация или список? | `PaginatedResponse[T]` → `data["items"]` |
| 4 | Какая роль нужна: MASTER или ADMIN? | `require_master` vs `require_super_admin` |
| 5 | Правильный ли путь к API? | `router.py` — проверь порядок роутов |

**Если ответ на любой вопрос "не уверен" — открой соответствующий файл и проверь.**

---

### 1. 🔴 КРИТИЧНО: `flush()` перед созданием связанных объектов

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

**Когда нужно:** При создании ANY связанной сущности (MasterProfile, ClientProfile, Appointment, Review и т.д.)

---

### 2. 🔴 КРИТИЧНО: Всегда указывайте `role` в тестовых данных

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

**Когда нужно:** При регистрации через API (`/register`, `/auth/register`)

---

### 3. 🔴 КРИТИЧНО: Создавайте пользователей напрямую в БД для fixtures

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

**Правило:** Если endpoint не найден (404), откройте `router.py` и проверьте порядок регистрации роутов.

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
- `GET /api/v1/admin/audit-logs`

**Endpoints БЕЗ пагинации (возвращают один объект или список):**
- `GET /api/v1/admin/services/all`
- `POST /api/v1/services/` (возвращает один объект)
- `POST /api/v1/auth/register` (возвращает один объект)

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

### 11. ✅ Bulk endpoints: Pydantic модель для Body

**Плохо:**
```python
@router.post("/bulk/toggle-active")
async def bulk_toggle_active(
    master_ids: List[int],  # ❌ FastAPI считает это query параметром
    ...
):
```

**Хорошо:**
```python
class MasterIdsRequest(BaseModel):
    master_ids: List[int]

@router.post("/bulk/toggle-active")
async def bulk_toggle_active(
    data: MasterIdsRequest,  # ✅ Pydantic модель
    ...
):
    master_ids = data.master_ids
```

**Почему:** Без `Body()` FastAPI интерпретирует `List[int]` как query параметр → 422. С `Body(..., embed=True)` нужен Pydantic wrapper.

**В тесте:**
```python
resp = await client.post("/api/v1/admin/bulk/toggle-active", 
    json={"master_ids": [1, 2, 3]},  # ✅ Объект, не массив
    headers=headers
)
```

---

### 12. ✅ Порядок регистрации роутов в FastAPI важен!

**Проблема:** Если `masters_router` (с prefix `/masters`) зарегистрирован ДО `bulk_router`, то путь `/api/v1/admin/bulk/...` будет перехвачен маршрутом `/api/v1/admin/masters/{master_id}/...` и `bulk` станет значением `{master_id}` → 404.

**Плохо:**
```python
router.include_router(masters_router)   # ❌ Сначала masters
router.include_router(bulk_router)      # ❌ bulk никогда не достучится
```

**Хорошо:**
```python
router.include_router(bulk_router)      # ✅ Сначала bulk (без {id})
router.include_router(masters_router)   # ✅ Потом masters (с {id})
```

**Правило:** Всегда регистрируй роуты БЕЗ `{param}` ДО роутов С `{param}`.

---

### 13. ✅ Проверяй роль для admin endpoints

Некоторые admin endpoints требуют **ADMIN**, а не просто MASTER.

**Плохо:**
```python
async def test_audit_logs(self, client, auth_headers):  # ❌ auth_headers = MASTER
    resp = await client.get("/api/v1/admin/audit-logs", headers=auth_headers)
    assert resp.status_code == 200  # ❌ 403 Forbidden
```

**Хорошо:**
```python
async def test_audit_logs(self, client, super_admin_headers):  # ✅ ADMIN
    resp = await client.get("/api/v1/admin/audit-logs", headers=super_admin_headers)
    assert resp.status_code == 200  # ✅
```

**Как проверить:** Открой router.py и посмотри, какой dependency используется:
- `require_master` — подходит и MASTER, и ADMIN
- `require_super_admin` — только ADMIN

---

### 14. ✅ Bulk toggle/suspend/unsuspend требуют MasterProfile IDs

Bulk endpoints (`/bulk/toggle-active`, `/bulk/suspend`, `/bulk/unsuspend`) ожидают `master_profile.id`, а не `user.id`.

**Плохо:**
```python
# ❌ user.id != master_profile.id
resp = await client.post("/api/v1/admin/bulk/toggle-active", 
    json={"master_ids": [user_id]},  # ❌ user.id
    headers=headers
)
```

**Хорошо:**
```python
# ✅ master_profile.id
# Регистрация возвращает master_profile.id в ответе
resp = await client.post("/api/v1/auth/register", json=reg_data)
master_profile_id = resp.json()["master_profile_id"]

resp = await client.post("/api/v1/admin/bulk/toggle-active", 
    json={"master_ids": [master_profile_id]},  # ✅ master_profile.id
    headers=headers
)
```

---

### 15. ✅ Session fixture использует commit(), а не rollback()

**Почему:** `session` fixture делает `commit()` после yield. Это означает:
- Данные, созданные в тесте, видны в том же тесте (через тот же session)
- После yield данные коммичатся в БД (для SQLite это не проблема)

**Что это значит для тестов:**
- Создаёшь запись через `session.add()` → она видна в `httpx.AsyncClient` запросах внутри того же теста
- Не нужно делать `rollback()` — данные сохраняются

**Пример:**
```python
async def test_something(self, client, session):
    # Создаём данные в той же сессии
    user = User(...)
    session.add(user)
    await session.flush()
    
    # Эти данные видны через HTTP клиент в том же тесте!
    resp = await client.get("/api/v1/admin/masters", headers=headers)
    assert resp.status_code == 200
```

---

### 16. ⚠️ Redis тесты требуют работающего Redis

Тесты `test_cache_service.py` и `test_reviews.py` используют Redis. Если Redis не запущен:
- `test_cache_service.py` — падает с connection error
- `test_reviews.py` — падает с 8 errors

**Решение:** Запустить Redis локально или использовать `pytest.mark.skipif` для пропуска этих тестов.

---

### 17. ⚠️ Refresh токены и password security требуют понимания бизнес-логики

Некоторые тесты (`test_refresh_tokens.py`, `test_password_security.py`) падают не из-за ошибок в тестах, а из-за несоответствия между ожидаемым поведением и реальной реализацией.

**Подход:**
1. Откройте файл с тестом
2. Откройте соответствующий production-файл
3. Сравните ожидаемое поведение с реальным
4. Либо исправьте production-код (если это баг), либо исправьте тест (если реализация намеренная)

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
- `GET /api/v1/admin/audit-logs`

**Endpoints БЕЗ пагинации (возвращают один объект или список):**
- `GET /api/v1/admin/services/all`
- `POST /api/v1/services/` (возвращает один объект)
- `POST /api/v1/auth/register` (возвращает один объект)

**Как проверить:** Всегда смотри router.py — если response_model=`PaginatedResponse[T]`, значит нужна обёртка `["items"]`.

---

### 14. ✅ Bulk endpoints: json={master_ids: [...]} а не json=[...]

**Плохо:**
```python
resp = await client.post("/api/v1/admin/bulk/toggle-active", 
    json=[1, 2, 3],  # ❌ Ожидается объект {"master_ids": [...]}
    headers=headers
)
```

**Хорошо:**
```python
resp = await client.post("/api/v1/admin/bulk/toggle-active", 
    json={"master_ids": [1, 2, 3]},  # ✅ Pydantic модель
    headers=headers
)
```

**Почему:** Bulk endpoints используют Pydantic модель `MasterIdsRequest` с полем `master_ids`.

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

### 11. ✅ Bulk endpoints требуют Pydantic модель для Body

**Плохо:**
```python
@router.post("/bulk/toggle-active")
async def bulk_toggle_active(
    master_ids: List[int],  # ❌ FastAPI считает это query параметром
    ...
):
```

**Хорошо:**
```python
class MasterIdsRequest(BaseModel):
    master_ids: List[int]

@router.post("/bulk/toggle-active")
async def bulk_toggle_active(
    data: MasterIdsRequest,  # ✅ Pydantic модель
    ...
):
    master_ids = data.master_ids
```

**Почему:** Без `Body()` FastAPI интерпретирует `List[int]` как query параметр → 422. С `Body(..., embed=True)` нужен Pydantic wrapper.

**В тесте:**
```python
resp = await client.post("/api/v1/admin/bulk/toggle-active", 
    json={"master_ids": [1, 2, 3]},  # ✅ Объект, не массив
    headers=headers
)
```

---

### 12. ✅ Порядок регистрации роутов в FastAPI важен!

**Проблема:** Если `masters_router` (с prefix `/masters`) зарегистрирован ДО `bulk_router`, то путь `/api/v1/admin/bulk/...` будет перехвачен маршрутом `/api/v1/admin/masters/{master_id}/...` и `bulk` станет значением `{master_id}` → 404.

**Плохо:**
```python
router.include_router(masters_router)   # ❌ Сначала masters
router.include_router(bulk_router)      # ❌ bulk никогда не достучится
```

**Хорошо:**
```python
router.include_router(bulk_router)      # ✅ Сначала bulk (без {id})
router.include_router(masters_router)   # ✅ Потом masters (с {id})
```

**Правило:** Всегда регистрируй роуты БЕЗ `{param}` ДО роутов С `{param}`.

---

### 13. ✅ Проверяй роль для admin endpoints

Некоторые admin endpoints требуют **ADMIN**, а не просто MASTER.

**Плохо:**
```python
async def test_audit_logs(self, client, auth_headers):  # ❌ auth_headers = MASTER
    resp = await client.get("/api/v1/admin/audit-logs", headers=auth_headers)
    assert resp.status_code == 200  # ❌ 403 Forbidden
```

**Хорошо:**
```python
async def test_audit_logs(self, client, super_admin_headers):  # ✅ ADMIN
    resp = await client.get("/api/v1/admin/audit-logs", headers=super_admin_headers)
    assert resp.status_code == 200  # ✅
```

**Как проверить:** Открой router.py и посмотри, какой dependency используется:
- `require_master` — подходит и MASTER, и ADMIN
- `require_super_admin` — только ADMIN

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

### Проблема 5: 403 Forbidden на admin endpoints

**Симптом:**
```
assert resp.status_code == 200  # ❌ 403 Forbidden
```

**Причина:** Endpoint требует `require_super_admin`, а тест использует `auth_headers` (MASTER role).

**Решение:** Использовать `super_admin_headers` для endpoints, требующих ADMIN.

**Где встречается:** `test_admin_dashboard.py`, `test_admin_audit.py`

---

### Проблема 6: Bulk endpoints ожидают master_profile.id, а не user.id

**Симптом:**
```
assert resp.status_code == 200  # ❌ 404 или пустой список
```

**Причина:** Bulk endpoints (`/bulk/toggle-active`, `/bulk/suspend`, `/bulk/unsuspend`) ищут по `master_profile.id`.

**Решение:** Использовать `master_profile.id` из ответа регистрации, а не `user.id`.

**Где исправлено:** `test_masters_bulk.py`

---

### Проблема 7: Route conflict — bulk routes не достижимы

**Симптом:**
```
assert resp.status_code == 200  # ❌ 404 для /api/v1/admin/bulk/toggle-active
```

**Причина:** `bulk_router` был зарегистрирован ПОСЛЕ `masters_router`, поэтому путь `/api/v1/admin/bulk/...` перехватывался маршрутом `/api/v1/admin/masters/{master_id}/...`.

**Решение:** Зарегистрировать `bulk_router` ДО `masters_router` в admin router.

**Где исправлено:** `app/modules/admin/router.py`

---

### Проблема 8: Pydantic модель для bulk endpoints

**Симптом:**
```
assert resp.status_code == 200  # ❌ 422 Unprocessable Entity
```

**Причина:** Bulk endpoints ожидают объект `{"master_ids": [...]}`, а не массив `[1, 2, 3]`.

**Решение:** Использовать `json={"master_ids": [1, 2, 3]}` в тесте.

**Где исправлено:** `app/modules/admin/masters/bulk.py` — добавлена Pydantic модель `MasterIdsRequest`

---

### Проблема 9: HTTPException попадает в validation_exception_handler

**Симптом:**
```
AttributeError: 'HTTPException' object has no attribute 'errors'
```

**Причина:** Кастомный handler 422 ошибок (`validation_exception_handler`) вызывает `.errors()` на ВСЕХ исключениях, включая `HTTPException(status_code=422)`, который raised вручную в production code. `HTTPException` не имеет метода `.errors()`.

**Решение:** Проверить `isinstance(exc, ValidationError)` перед вызовом `.errors()`.

**Где исправлено:** `app/main.py` — добавлена проверка `isinstance(exc, ValidationError)`

---

### Проблема 10: UnboundLocalError из-за локального импорта

**Симптом:**
```
UnboundLocalError: cannot access local variable 'User' where it is not associated with a value
```

**Причина:** В функции есть `from app.models.user import User` (локальный импорт), но `User` используется ДО этого импорта в том же блоке кода. Python видит локальную переменную `User` и считает, что она должна быть локальной для всей функции, но к моменту первого использования она ещё не присвоена.

**Решение:** Удалить дублирующий локальный импорт — `User` уже импортирован на уровне модуля.

**Где исправлено:** `app/modules/booking/router.py` — удалён `from app.models.user import User` на строке 69

---

### Проблема 11: Timezone-aware vs naive datetime comparison

**Симптом:**
```
TypeError: can't compare offset-naive and offset-aware datetimes
```

**Причина:** SQLite хранит DateTime как строку без timezone info. При чтении через SQLAlchemy результат может быть naive datetime. Сравнение `naive_datetime < aware_datetime` вызывает TypeError.

**Решение:** Проверить `expires_at.tzinfo` и добавить timezone если нужно.

**Где исправлено:** `app/modules/auth/router.py` — проверка `expires_at.tzinfo is None` перед сравнением

---

### Проблема 12: Duplicate email вызывает IntegrityError вместо 409

**Симптом:**
```
IntegrityError: UNIQUE constraint failed: users.email
```

**Причина:** Production code не проверяет дубликат email перед вставкой. При дублировании бд бросает IntegrityError, который не обрабатывается и падает с 500.

**Решение:** Добавить проверку дубликата email перед INSERT и вернуть 409 Conflict.

**Где исправлено:** `app/modules/user/router.py` — добавлена проверка duplicate email

---

## Актуальная статистика (v8 — 2026-10-01 21:00)

| Метрика | Значение |
|--------|---------|
| ✅ PASSED | **238** |
| ❌ FAILED | **0** |
| ⏭️ SKIPPED | **0** |
| ⚠️ ERROR | 0 |
| **Всего** | **238** |

**Покрытие:** 238 тестов, ~20000+ строк тестового кода, 22 test files.

### Пройденные файлы (100% PASS) — 22 файла:
- `test_admin_appointments.py` — 16/16 ✅
- `test_admin_audit.py` — 4/4 ✅
- `test_admin_clients.py` — 11/11 ✅
- `test_admin_dashboard.py` — 4/4 ✅
- `test_admin_services.py` — 9/9 ✅
- `test_admin_working_hours.py` — 10/10 ✅
- `test_appointments.py` — 10/10 ✅
- `test_auth.py` — 8/8 ✅
- `test_auth_dependencies.py` — 10/10 ✅
- `test_auth_service.py` — 12/12 ✅
- `test_auth_tokens.py` — 12/12 ✅
- `test_cache_service.py` — 18/18 ✅
- `test_clients.py` — 9/9 ✅
- `test_health.py` — 3/3 ✅
- `test_masters.py` — 10/10 ✅
- `test_masters_bulk.py` — 6/6 ✅
- `test_masters_crud.py` — 17/17 ✅
- `test_masters_status.py` — 11/11 ✅
- `test_password_security.py` — 11/11 ✅ (0 skipped, was 6)
- `test_rate_limiting.py` — 9/9 ✅
- `test_refresh_tokens.py` — 5/5 ✅
- `test_reviews.py` — 12/12 ✅ (0 skipped, was 9)
- `test_schedule.py` — 7/7 ✅
- `test_services.py` — 7/7 ✅

---

## CI/CD и деплой

### GitHub Actions Workflow (`.github/workflows/deploy.yml`)

**Порядок выполнения при push в main:**

1. **Test job** — запускает тесты в CI
   - Устанавливает Python 3.11 и зависимости
   - Запускает `pytest` с coverage
   - Показывает summary: passed/failed/skipped/coverage
   - **Если тесты падают — деплой отменяется**

2. **Deploy job** — запускается ТОЛЬКО если тесты прошли
   - SSH на сервер
   - **Database backup** — создаёт timestamped SQL dump
   - **Test job on server** — запускает тесты перед деплоем
   - **Alembic migrations** — применяет миграции БД
   - **Superuser creation** — создаёт админа если нет
   - **Seed data** — заполняет начальные данные
   - **Frontend build** — собирает фронтенд
   - **Service restart** — перезапускает backend и nginx
   - **Health check** — 3 попытки проверки здоровья API
   - **API verification** — проверяет ключевые endpoints

### Safety Gates

| Gate | Что делает | Что происходит при fail |
|------|-----------|------------------------|
| CI tests | Тесты в GitHub Actions | Деплой отменяется |
| Server tests | Тесты на сервере перед restart | Деплой abort, сервис не перезапускается |
| DB backup | SQL dump перед миграциями | Продолжает (warn), но есть бэкап |
| Health check | 3 попытки проверки /health | Warning, но деплой завершается |

### Coverage

```bash
# Локально с coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# На сервере автоматически при деплое
PYTHONPATH=. pytest tests/ -v --cov=app --cov-report=term-missing
```

### Пропущенные тесты (SKIPPED):
- `test_password_security.py` — 6 skipped (password validation not implemented in API yet)
- `test_reviews.py` — 9 skipped (references non-existent `app.models.client` — needs rewrite)

### Исправленные production-баги:
1. `_find_or_create_client` — добавлен `flush` перед созданием ClientProfile
2. `mark_no_show` — исправлен запрос: `ClientProfile.user_id` вместо `ClientProfile.id`
3. `delete_admin_client` — добавлено удаление ClientProfile перед User
4. `book_appointment` — добавлен импорт `joinedload`
5. `bulk_toggle_active/suspend/unsuspend` — добавлен `Body(..., embed=True)` через Pydantic модель
6. `bulk_router` — перемещён в admin router перед masters_router для исправления конфликта путей
7. `validation_exception_handler` — добавлена проверка `isinstance(ValidationError)` для HTTPException
8. `create_appointment` — удалён дублирующий локальный импорт `User` (UnboundLocalError)
9. `refresh_token` — исправлено сравнение timezone-aware/naive datetime
10. `create_client` — добавлена проверка duplicate email (409 вместо IntegrityError)
11. `WorkingHourCreate` — master_id сделан опционаальным (admin endpoints derive from auth)
12. `schedule/router.py` — убраны redundant `fromisoformat` вызовы (schema уже парсит time)
13. `UserCreate` — добавлена валидация пароля (min 8 chars, upper/lower/digit/special, 4 unique)
14. `UnifiedRegisterRequest` — добавлена валидация пароля (те же правила, что и UserCreate)

---

## Чек-лист перед написанием теста

**ПЕРЕД написанием любого теста проверьте:**

- [ ] `role` указан в тестовых данных для регистрации?
- [ ] `flush()` вызван перед созданием связанных объектов?
- [ ] Формат ответа API: пагинация (`data["items"]`) или список?
- [ ] Роль для авторизации: `super_admin_headers` или `auth_headers`?
- [ ] Путь к API правильный? (проверьте `router.py`)
- [ ] Для bulk endpoints: `json={"master_ids": [...]}` а не `json=[...]`?
- [ ] Для bulk endpoints: `master_profile.id` а не `user.id`?

**ПЕРЕД коммитом:**

- [ ] Все тесты проходят (`pytest tests/ -v --tb=no`)
- [ ] Нет `ERROR` в результатах (только `PASSED` или `FAILED`)
- [ ] Фикстуры используют `flush()` перед созданием связанных объектов
- [ ] Тестовые данные включают `role` поле
- [ ] Используется class-based структура для группировки
- [ ] Путь к API правильный (проверьте `router.py`)
- [ ] Телефон отформатирован правильно (если нужно)
- [ ] Нет хардкода ID (используйте фикстуры)

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

---

## Чек-лист перед коммитом тестов

> ⚠️ **Этот чек-лист дублирует чек-лист из раздела "Критические правила".** Используйте его для финальной проверки перед коммитом.

- [ ] Все тесты проходят (`pytest tests/ -v --tb=no`)
- [ ] Нет `ERROR` в результатах (только `PASSED` или `FAILED`)
- [ ] Фикстуры используют `flush()` перед созданием связанных объектов
- [ ] Тестовые данные включают `role` поле
- [ ] Используется class-based структура для группировки
- [ ] Путь к API правильный (проверьте `router.py`)
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

---

## Устранение неполадок

### CI/CD проблемы

#### CI падает с "module not found" или "cd: no such file"

**Причина:** Неверный путь к backend в `ci.yml` или `deploy.yml`.

**Решение:**
```yaml
# ❌ Неправильно:
cd backend

# ✅ Правильно:
cd online-booking/backend
```

**Проверка:**
```bash
# Убедитесь, что путь существует:
ls online-booking/backend/tests/
ls online-booking/backend/requirements.txt
```

#### CI падает с "No tests collected"

**Причина:** pytest не находит тесты из-за неправильного рабочего каталога.

**Решение:** Убедитесь, что `cd online-booking/backend` выполнен ПЕРЕД запуском pytest.

#### Серверные тесты падают на деплое

**Причина:** grep-паттерн в `deploy.yml` ловит `error` из coverage-отчёта (например, `test_cache_get_handles_decode_error`), а не из итогов тестов.

**Решение:** Использовать точный паттерн для итоговой строки pytest:
```bash
# ❌ Неправильно — ловит "error" из coverage:
grep -E "passed|failed|error|skipped|coverage" test-results.txt | tail -5

# ✅ Правильно — только итоговая строка:
grep "passed.*in" test-results.txt | tail -1
```

**Проверка:**
```bash
# Убедитесь, что итоговая строка содержит только summary:
grep "passed.*in" /tmp/test-results.txt
# Должно быть: "238 passed, 0 failed in 466s"
```

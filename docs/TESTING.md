# Тестирование

> Backend: 41 файл, 334 теста (pytest, SQLite-файл на тест). Frontend: 16 файлов, 77 тестов (Vitest).
> Чек-лист перед коммитом — только в [RULES.md](RULES.md), правила деплоя — в [DEPLOYMENT_RULES.md](DEPLOYMENT_RULES.md).

## Запуск

```powershell
# Backend (322 passed, ~4 мин)
cd online-booking\backend
$env:PYTHONPATH='.'
pytest tests/ -v                          # всё
pytest tests/test_reviews.py -v           # один файл
pytest tests/ -q --cov=app --cov-report=term-missing --cov-fail-under=55  # с гейтом (как в CI)

# Frontend (78 passed, ~5 сек)
cd online-booking\frontend
npx vitest run                            # всё
npx tsc --noEmit                          # типы (обязательно: ловят то, что тесты не ловят)
npx eslint src/                           # 0 errors (warnings по `any` — pre-existing)
npx prettier --check src/                 # стиль (конфиг .prettierrc.json)
```

## Backend: архитектура тестов

- `conftest.py`: `engine` (уникальный SQLite-файл на тест, function scope) → `session`
  (коммит, не rollback — данные видны внутри теста) → `client` (httpx+ASGITransport,
  `get_db` переопределён). Async-фикстуры — `@pytest_asyncio.fixture`, `asyncio_mode=auto`.
- `RATE_LIMIT_DISABLED=true` ставится в `conftest.py` до импорта app (иначе slowapi даст 429
  на 100+ запросах) и в CI явно.
- In-memory изоляции нет осознанно — файловый SQLite ближе к проду; тесты последовательны.
- Helper-фикстуры: `test_master_data` (с `role: "MASTER"`), `created_master_id` (flush),
  `super_admin_headers` / `auth_headers`, `psession` (для pull-скриптов).

## Backend: 5 вопросов перед каждым тестом

| # | Вопрос | Ответ |
|---|--------|-------|
| 1 | `role` в тестовых данных? | `schemas/user.py::UserCreate` — обязателен |
| 2 | `flush()` перед связанными объектами? | Есть FK — да |
| 3 | Пагинация или список? | `PaginatedResponse` → `data["items"]`, иначе список |
| 4 | MASTER или ADMIN? | `require_master` vs `require_super_admin` → `auth_headers` vs `super_admin_headers` |
| 5 | Путь правильный? | Порядок роутов в `router.py` (специфичные до `/{id}`) |

Плюс: связанные модели читать только с `selectinload`/`joinedload` (иначе `MissingGreenlet`
в async); `appointment.client_id` = `client_profiles.id`, bulk — `master_profile.id`
и `json={"master_ids": [...]}`; `HTTPException(422)` не путать с `RequestValidationError`.

## Backend: грабли (по одному разу, без дублей)

1. `MissingGreenlet` — lazy load в async невозможен: `selectinload` в запросе.
2. `new_user.id is None` — нужен `flush()` до чтения id.
3. 404 после создания — session fixture делает `commit`, не `rollback`.
4. 403 на admin-эндпоинтах — нужны `super_admin_headers`, не `auth_headers`.
5. Bulk 404 — `bulk_router` до `masters_router`; id — `master_profile.id`.
6. Bulk 422 — тело `{"master_ids": [...]}`, модель `MasterIdsRequest`.
7. `AttributeError: 'HTTPException' has no 'errors'` — проверять `isinstance(exc, ValidationError)`.
8. `UnboundLocalError` — локальный импорт затеняет модульный; удалять дубль.
9. naive vs aware datetime (SQLite) — проверять `tzinfo`, см. `utils/__init__.py::ensure_utc`.
10. Duplicate email → проверять до INSERT, отдавать 409 (не 500).
11. Дубли имён тестов в одном файле — второй silently затеняет первый (было:
    `test_toggle_admin_self` ×2, `test_email_conflict_skips_row` ×2; переименованы).
12. `client_profiles.user_id NOT NULL` — сначала User+flush, потом профиль.

## Backend: файлы (сгенерировано, 322 всего)

| Файл | N | Файл | N |
|---|---|---|---|
| test_admin_appointments.py | 16 | test_import_csv.py | 6 |
| test_admin_audit.py | 4 | test_log_level.py | 3 |
| test_admin_clients.py | 11 | test_master_mutations.py | 7 |
| test_admin_dashboard.py | 4 | test_master_stats.py | 6 |
| test_admin_working_hours.py | 11 | test_master_tariff_status.py | 14 |
| test_appointments.py | 10 | test_masters.py | 10 |
| test_appointments_filters.py | 2 | test_masters_bulk.py | 6 |
| test_auth.py | 9 | test_masters_crud.py | 19 |
| test_auth_dependencies.py | 10 | test_masters_security.py | 11 |
| test_auth_service.py | 13 | test_masters_status.py | 12 |
| test_auth_tokens.py | 12 | test_password_security.py | 11 |
| test_booking_flow.py | 7 | test_pull_production.py | 12 |
| test_cache_service.py | 19 | test_rate_limiting.py | 3 |
| test_cities_resolve.py | 2 | test_refresh_tokens.py | 5 |
| test_clients.py | 9 | test_reviews.py | 12 |
| test_create_superuser.py | 4 | test_schedule.py | 7 |
| test_dadata_proxy.py | 5 | test_services.py | 8 |
| test_export_tasks.py | 4 | test_validation_handler.py | 2 |
| test_fix_production_db.py | 2 | test_work_window.py | 2 |
| test_health.py | 3 | | |

## Frontend: файлы (77 всего)

Покрыто: `apiError`, `authRefresh` (очередь 401), `CitySelect`, `ClientsFilter`, `dadata`,
`helpers` (schedule), schedule `hooks`, `impersonation`, `MasterSelect`,
`maxAuth` (MAX-вкладка: код + автовход), `Modal`/`ConfirmDialog`, `Pager`, `PhoneInput`, `section`, `SuperAdminLayout`,
`StatusBadge`/`useAdminSort`. Не покрыто (сознательно): большие страницы и роутинг-гарды —
их держит `tsc --noEmit` + ручной смоук.

## CI/CD гейты

| Gate | Где | Fail → |
|---|---|---|
| pytest 322 + `--cov-fail-under=55` | `ci.yml` backend-tests | PR/деплой blocked |
| eslint (0 errors) + `tsc --noEmit` + `vitest run` + `prettier --check` | `ci.yml` frontend-lint | PR/деплой blocked |
| pytest на сервере до restart | `deploy.yml` | deploy abort |
| pg_dump перед миграциями | `deploy.yml` | warn, continue |

## Новый тест: шаблон

```python
class TestSomething:
    async def test_empty_list(self, client, super_admin_headers):
        resp = await client.get("/api/v1/admin/things", headers=super_admin_headers)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
```

Class-based группировка, фикстуры вместо хардкода id, `role` в данных, `flush()` перед
связями, уникальные имена (см. грабли №11).

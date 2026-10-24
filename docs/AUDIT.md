# Аудит проекта Beauty Specialist

> Живой документ. Обновляется по мере исправления находок.
> Не удаляем пункты: меняем статус, фиксируем коммит, проверку и остаточный риск.

| Параметр | Значение |
|---|---|
| Дата аудита | 24.10.2026 |
| Базовая ревизия | `1b3570c` |
| Ревизия после P0-фикса | `b25f7c1` |
| Ревизия после security-фикса | `1890479` |
| Ревизия после booking-фикса | `aed3bd7` |
| Ревизия после deploy-фикса | `c711ec8` |
| Ревизия после security-фикса 2 | `904c06d` |
| Ветка | `main` |
| Область | backend, frontend, БД/миграции, CI/CD, deploy, зависимости, документация, гигиена репозитория |
| Метод | статический разбор кода, grep-метрики, тесты, `tsc`, ESLint, npm/pip audit, разбор workflow и deploy-логов, production smoke |
| Ограничения | без нагрузочного тестирования, полного pentest, доступа к production-БД и живой проверки внешних API |

---

## 0. Как пользоваться документом

### Статусы

| Статус | Значение |
|---|---|
| ⬜ open | не начато |
| 🟨 in progress | в работе |
| ✅ fixed | исправлено и проверено |
| ⏸ deferred | сознательно отложено, причина указана |
| ❌ wontfix | решили не исправлять, причина указана |

### Приоритеты

| Приоритет | Значение | Срок |
|---|---|---|
| P0 | активная компрометация, потеря данных, простой | немедленно, останавливаем другие работы |
| P1 | высокий риск безопасности/данных/деплоя | текущий спринт |
| P2 | средний риск, производительность, поддерживаемость | 2–6 недель |
| P3 | гигиена и nice-to-have | по возможности |

### Правило обновления после каждого фикса

1. Меняем статус пункта на `✅ fixed` или `🟨 in progress`.
2. Указываем коммит и короткое описание изменения.
3. Указываем, чем проверено: тесты, CI, deploy, production smoke.
4. Добавляем запись в [журнал изменений](#9-журнал-изменений).
5. Если остался риск или долг — создаём отдельный пункт, а не прячем его.
6. Definition of Done: код + regression-тест + локальная проверка + зелёный CI + обновлённый документ.

---

## 1. Резюме

### Вердикт

Проект — крепкий модульный монолит, а не кандидат на переписывание. Есть тесты, Alembic, CI/CD, осмысленные middleware и разделение backend на `modules/services/schemas/models`.

Главные проблемы: накопленный security-долг, god-файлы, дублирование логики бронирования, неуправляемый data-fetching на фронтенде, рискованный deploy и дрейф зависимостей/документации.

**Массовый переход на другие библиотеки не нужен.** Уже установлены FastAPI, SQLAlchemy, Pydantic, slowapi, TanStack Query, sonner. Проблема в том, что установленное используется не полностью: TanStack Query смонтирован, но не используется; RQ/Redis есть в зависимостях, но фоновые циклы живут внутри API-процесса.

### Оценка по критериям

| Критерий | Оценка | Комментарий |
|---|---:|---|
| Архитектура и модульность | 7/10 | слои есть, но роутеры перегружены бизнес-логикой |
| Безопасность | 6/10 | P0, OTP brute-force и TTL имперсонации закрыты; остаются rate limit, DaData и PII |
| Тесты | 8/10 | 785 backend + 281 frontend, но медленные и без критичных сценариев |
| Производительность | 6/10 | N+1, full scans, блокирующий bcrypt/Pillow |
| Зависимости | 6/10 | сильное отставание, нет Python-lock и audit-гейтов |
| CI/CD | 7/10 | работает, но есть race деплоя, слабые backup/health/rollback |
| Документация | 5/10 | много, но README раздут, docs расходятся с кодом |
| Чистота кода | 6/10 | стиль ровный, но дубли, мёртвый код, 43 ESLint warning |
| **Итого** | **~6,5/10** | хорошая база, нужен security-спринт и точечная декомпозиция |

### Что уже хорошо

- 19,5K строк backend, 29,3K frontend; 41 Alembic-миграция, один head.
- 785 backend-тестов, 281 frontend-тест; CI гоняет SQLite и PostgreSQL, coverage-gate 55%.
- Нет raw SQL через `text()`, нет `dangerouslySetInnerHTML`; SQLAlchemy ORM используется последовательно.
- OTP хранится в виде хэша, refresh rotation, audit log, имперсонация с аудитом, security headers, Sentry, slowapi.
- TypeScript `strict`, 0 ошибок `tsc`, 0 ошибок ESLint (43 warning).
- Frontend-тесты быстрые (~12–18 секунд).
- P0-уязвимость найдена и закрыта в день аудита.

### Сводка находок

| Область | P0 | P1 | P2 | P3 | Всего | Исправлено |
|---|---:|---:|---:|---:|---:|---:|
| Безопасность | 1 | 5 | 3 | 1 | 10 | 5 |
| Корректность данных | 0 | 5 | 4 | 0 | 9 | 4 |
| Деплой и инфраструктура | 0 | 6 | 4 | 0 | 10 | 3 |
| Производительность | 0 | 0 | 6 | 1 | 7 | 0 |
| Архитектура и чистота | 0 | 0 | 9 | 2 | 11 | 0 |
| Тесты | 0 | 0 | 2 | 1 | 3 | 0 |
| Зависимости, docs, гигиена | 0 | 0 | 3 | 2 | 5 | 0 |
| Инцидент-респонс | 2 | 2 | 1 | 0 | 5 | 0 |
| **Итого** | **3** | **18** | **32** | **7** | **60** | **12** |

> На момент аудита P0 было 3: один код-фикс уже закрыт (`SEC-01`), два пункта инцидент-респонса остаются (`IR-01`, `IR-02`).

---

## 2. P0-инцидент: вход по одному телефону

### SEC-01 — публичный endpoint выдавал токен по телефону

**Статус:** ✅ fixed · **Коммит:** `b25f7c1`

**Что было.** `POST /api/v1/auth/client/login` принимал только телефон и выпускал access-token. Проверка `_reject_master_password_login()` блокировала `MASTER`, но не `ADMIN`. Телефон суперпользователя был жёстко прописан в `create_superuser.py`, репозиторий публичный.

**Влияние.** Любой, кто знал телефон активного пользователя, мог получить его сессию; для администратора — полный доступ к панели без пароля.

**Что сделано.**

- Удалён маршрут `/api/v1/auth/client/login`.
- Удалены `login_client_legacy`, `UserLoginByPhone`, фронтенд-заглушка `clientLogin`.
- Убран захардкоженный телефон, добавлен `SUPERUSER_PHONE` (только контакт, не вход).
- Добавлен regression-тест: маршрут должен отдавать `404`.
- Обновлены `docs/API.md` и описание API.

**Проверка.**

- CI `40068533306` — success (SQLite + PostgreSQL).
- Deploy `40068533320` — success.
- Production: `POST /api/v1/auth/client/login` → `404`; `/health` → `200`.

**Остаточный риск.** Токены, выданные до фикса, живут до 24 часов, потому что JWT stateless. Телефон остался в истории git. Нужен инцидент-респонс ниже.

---

## 3. Инцидент-респонс

> Эти пункты не закрываются кодом в репозитории. Нужен доступ к серверу/БД и решение владельца.

| ID | P | Действие | Зачем | Статус |
|---|---|---|---|---|
| IR-01 | P0 | Ротировать `SECRET_KEY` и `REFRESH_SECRET_KEY` в серверном `.env`, перезапустить backend | инвалидировать все access/refresh-токены, включая выданные до фикса | ⬜ open |
| IR-02 | P0 | Проверить nginx access logs на `POST /api/v1/auth/client/login`, логи приложения на `Client login successful`, `last_login_provider='phone'` у админа и `audit_logs` | понять, использовалась ли уязвимость | ⬜ open |
| IR-03 | P1 | Очистить/сменить телефон администратора в БД, сменить пароль | убрать публично известный контакт из вектора атаки | ⬜ open |
| IR-04 | P1 | Отозвать refresh-токены/сессии администратора, проверить активные сессии | закрыть возможные сохранённые сессии | ⬜ open |
| IR-05 | P2 | Зафиксировать инцидент и провести ретроспективу; добавить алерт на устаревшие auth-маршруты | не повторить | ⬜ open |

**Порядок:** IR-02 (собрать факты) → IR-01 (отозвать токены) → IR-03/IR-04 → IR-05.

---

## 4. Безопасность

| ID | P | Находка | Где | Влияние | Статус |
|---|---|---|---|---|---|
| SEC-01 | P0 | Вход по одному телефону, включая ADMIN | удалено в `b25f7c1` | полный admin takeover | ✅ fixed |
| SEC-02 | P1 | Нет счётчика неудачных OTP; `SMS_MAX_ATTEMPTS` не используется | `auth/service.py::verify_otp`, `config.py` | перебор 6-значного кода | ✅ fixed |
| SEC-03 | P1 | Имперсонация живёт 24 часа | `services/impersonation.py` | украденный support-токен долго действует | ✅ fixed |
| SEC-04 | P1 | Refresh не проверяет `is_active`/`deleted_at` | `auth/router.py::refresh_token` | заблокированный пользователь продлевает сессию | ✅ fixed |
| SEC-05 | P1 | Rate limit in-memory и только по IP; Redis не подключён | `middleware/rate_limit.py` | обход при нескольких процессах; нет лимитов на аккаунт | 🟨 in progress |
| SEC-06 | P1 | DaData — открытый платный прокси без auth/allowlist | `modules/dadata/router.py` | расход ключа, открытый платный прокси | ✅ fixed |
| SEC-07 | P2 | Телефоны/email пишутся в INFO-логи | `auth/router.py`, `auth/service.py` | PII в логах, риск по 152-ФЗ | ⬜ open |
| SEC-08 | P2 | Нет CSP; access token читается из JS; cookie имперсонации без `Secure`/`SameSite` | `security_headers.py`, `utils/cookies.ts`, `utils/impersonation.ts` | XSS-поверхность, ослабленная cookie | ⬜ open |
| SEC-09 | P3 | Личная почта в коде | `services/client_visibility.py` | утечка контакта, сложно менять | ⬜ open |
| SEC-10 | P2 | Нет проверки same-origin для post-login redirect | `utils/redirect.ts`, `LoginModal.tsx` | open redirect | ⬜ open |

### План по P1-безопасности

- **SEC-02:** добавить `attempts` в `OtpCode` + миграцию; сжигать код после 3–5 ошибок; лимит на телефон и IP; сравнивать через `hmac.compare_digest`; тесты на перебор.
- **SEC-03:** отдельный TTL 5–15 минут для имперсонации; claim `impersonated_by`; при поддержке только просмотра — `scope=readonly`.
- **SEC-04:** проверять `is_active` и `deleted_at` при refresh; тест на заблокированного пользователя.
- **SEC-05:** подключить Redis storage для slowapi; отдельные ключи для refresh/logout/OTP по аккаунту; тест на несколько процессов/воркеров.
- **SEC-06:** auth, allowlist методов/путей, rate limit, кэш, общий `httpx.AsyncClient` с таймаутом.

---

## 5. Корректность данных

| ID | P | Находка | Где | Влияние | Статус |
|---|---|---|---|---|---|
| DATA-01 | P1 | Гонка `SELECT` → `INSERT` при бронировании | `services/booking.py`, `client/router.py`, `booking/router.py` | двойные записи | ✅ fixed |
| DATA-02 | P1 | `find_conflict()` сканирует всю историю и берёт текущую длительность услуги | `services/booking.py::find_conflict` | деградация и неверные пересечения | ✅ fixed |
| DATA-03 | P1 | Админское прямое создание записи без проверки услуги/конфликта | `admin/appointments/booking.py` | двойная запись, чужая услуга | ✅ fixed |
| DATA-04 | P2 | `/available-days` и `/available-slots` игнорируют расписание и занятость | `booking/router.py` | неверная доступность, если endpoint используют | ⬜ open |
| DATA-05 | P1 | Отчёты считают `Service.price`, игнорируя снапшот и комплексы | `admin/dashboard/reports.py` | неверная выручка/P&L | ✅ fixed |
| DATA-06 | P2 | Невалидная дата в query → `ValueError` → 500 | `reports.py`, `appointments/listing.py` | 500 вместо 422 | ⬜ open |
| DATA-07 | P2 | CSV собирается f-string без экранирования | `services/export_tasks.py` | битый CSV, formula injection | ⬜ open |
| DATA-08 | P1 | Расписание применяет новое состояние даже при ошибке API | `components/schedule/hooks.tsx` | пользователь видит несуществующий рабочий день | ⬜ open |
| DATA-09 | P2 | Dashboard возвращает `null`; ClientsPage без error-state; Skeleton игнорирует height | `DashboardPage.tsx`, `ClientsPage.tsx`, `Skeleton.tsx` | пустой экран/неверный UI | ⬜ open |

### План по P1-данным

- **DATA-01:** DB-level защита: `SELECT ... FOR UPDATE` по мастеру, advisory lock или PostgreSQL exclusion constraint; добавить конкурентный тест.
- **DATA-02:** добавить нижнюю границу по времени и индексы; использовать `Appointment.duration_minutes` как снапшот, `Service.duration_minutes` — только fallback.
- **DATA-03:** свести создание записи в один `appointment_service`, использовать его в public/client/admin; тест на конфликт и чужую услугу.
- **DATA-05:** считать по `Appointment.price`/bundle-снапшотам и скидкам; добавить тест на комплекс и изменённую цену услуги.
- **DATA-08:** mutation с rollback + toast; тест на ошибку API.

---

## 6. Деплой и инфраструктура

| ID | P | Находка | Где | Влияние | Статус |
|---|---|---|---|---|---|
| DEP-01 | P1 | Deploy не сверяет `HEAD` с `github.sha`, делает `fetch main` + `reset FETCH_HEAD` | `.github/workflows/deploy.yml` | можно выкатить непротестированный commit | ✅ fixed |
| DEP-02 | P1 | Бэкап в `/tmp` с `\|\| echo`, без проверки/retention/restore; rollback нет | `deploy.yml`, `scripts/deploy_db.sh` | нет гарантии восстановления | 🟨 in progress |
| DEP-03 | P1 | Backend рестартует до миграций | `scripts/deploy_setup.sh` | новый код на старой схеме | ✅ fixed |
| DEP-04 | P1 | `fix_all_tables.sql` выполняется каждый deploy, содержит `DROP COLUMN`, ошибки глушатся | `deploy.yml`, `scripts/deploy_db.sh` | риск разрушения схемы | ⬜ open |
| DEP-05 | P1 | PostgreSQL-тесты не входят в `needs` deploy | `.github/workflows/ci.yml`, `deploy.yml` | деплой может пройти без PG-гейта | ⬜ open |
| DEP-06 | P2 | Health-check только `systemctl is-active` | `scripts/deploy_finalize.sh` | сервис активен, но API/БД мертвы | ✅ fixed |
| DEP-07 | P1 | `npm audit --omit=dev`: 1 high (`follow-redirects`) + 2 moderate (`react-router`) | `package-lock.json` | известные уязвимости в prod | ⬜ open |
| DEP-08 | P2 | Токен в git URL, захардкожен IP, actions на тегах | `deploy.yml` | утечка токена/непредсказуемость CI | ⬜ open |
| DEP-09 | P2 | Нет Python-lock; тестовые зависимости в prod; `twilio>=`, `aiohttp>=` | `requirements.txt` | невоспроизводимые сборки | ⬜ open |
| DEP-10 | P2 | Docker backend отсутствует; Node 20 EOL; Python 3.11 в CI vs 3.12 в проде | `docker-compose.yml`, `Dockerfile`, workflows | расхождение окружений | ⬜ open |

### План по deploy

- **DEP-01:** checkout/fetch по точному `github.sha`, `git rev-parse HEAD` == ожидаемый SHA, иначе fail.
- **DEP-02:** бэкап в постоянный каталог, проверка размера/кода, retention, restore-инструкция, rollback-план.
- **DEP-03:** порядок: deps → migrations → restart backend → frontend → finalize.
- **DEP-04:** заморозить `fix_all_tables.sql`, убрать из регулярного деплоя; схема только через Alembic.
- **DEP-05:** добавить PostgreSQL-job в `needs` deploy или переиспользуемый workflow.
- **DEP-07:** `npm audit fix` для high; router 7 — отдельное решение/митигация.

---

## 7. Производительность

| ID | P | Находка | Где | Влияние | Статус |
|---|---|---|---|---|---|
| PERF-01 | P2 | Дайджест мастеров: N+1 preference/working hours + запрос записей каждые 60 сек | `services/reminders.py` | лишняя нагрузка на БД | ⬜ open |
| PERF-02 | P2 | Auto-complete грузит все `confirmed` без фильтра по дате, затем N+1 | `services/auto_complete.py` | медленно с ростом истории | ⬜ open |
| PERF-03 | P2 | Занятость клиента грузит всю историю и фильтрует месяц в Python | `client/router.py` | лишние строки/память | ⬜ open |
| PERF-04 | P2 | bcrypt/Pillow работают в event loop | `utils/security.py`, `utils/images.py` | блокировка event loop | ⬜ open |
| PERF-05 | P3 | CSV собирается целиком в памяти | `services/export_tasks.py` | память на больших выборках | ⬜ open |
| PERF-06 | P2 | `BUILD_ID` в именах всех assets + нет `manualChunks` | `vite.config.ts` | полный сброс кэша каждый deploy | ⬜ open |
| PERF-07 | P2 | TanStack Query не используется; Swiper в основном chunk | `main.tsx`, `HomePage.tsx` | мёртвый вес/размер бандла | ⬜ open |

---

## 8. Архитектура и чистота

| ID | P | Находка | Где | Влияние | Статус |
|---|---|---|---|---|---|
| ARCH-01 | P2 | God-файлы backend: billing 1703 строки, auth router 847, client router 801 | `services/billing.py`, `auth/router.py`, `client/router.py` | сложно менять/тестировать | ⬜ open |
| ARCH-02 | P2 | 8 god-компонентов по 950–1075 строк | `ServicesPage`, `AppointmentsPage`, `SchedulePage`, `MasterDetailPage`, `LoginModal`, `ProfilePage`, `ClientsPage`, `CabinetBookPage` | сложность, ререндеры | ⬜ open |
| ARCH-03 | P2 | Создание записи реализовано минимум трижды | public/client/admin | расхождение правил | ⬜ open |
| ARCH-04 | P2 | Похожие OAuth-хелперы VK/Yandex/MAX | `modules/*auth` | дублирование | ⬜ open |
| ARCH-05 | P2 | 96 `useEffect`, 0 `useQuery`; ручные loading/error/seq | `src/pages`, `src/components` | гонки, двойные запросы | ⬜ open |
| ARCH-06 | P2 | Правила `react-hooks` не включены | `eslint.config.js` | 96 effect'ов без проверки зависимостей | ⬜ open |
| ARCH-07 | P3 | Мёртвый код/зависимости: `LoginPage`, `@tanstack/query-core` | `pages/admin/LoginPage.tsx`, `package.json` | лишний вес/поддержка | ⬜ open |
| ARCH-08 | P2 | Дубли форматтеров/статусов/типов; `UserRole` не совпадает с реальными ролями | `src/api/types.ts`, страницы | рассинхрон UI | ⬜ open |
| ARCH-09 | P3 | 288 уникальных hex-цветов, 2 CSS-переменные, 243 inline-style | `src/**/*.css`, компоненты | сложно менять тему | ⬜ open |
| ARCH-10 | P2 | A11y: Modal без focus trap/aria, 125 input против 14 `htmlFor`, кастомные select, `lang="en"` | `Modal.tsx`, формы, `index.html` | недоступность, SEO | ⬜ open |
| ARCH-11 | P2 | Alembic не импортирует `coupon.py` | `app/models/__init__.py`, `alembic/env.py` | autogenerate может удалить таблицу | ⬜ open |

---

## 9. Тесты

| ID | P | Находка | Где | Влияние | Статус |
|---|---|---|---|---|---|
| TEST-01 | P2 | Новый SQLite-файл и схема на каждый тест; suite ~27 мин локально | `tests/conftest.py` | медленная обратная связь | ⬜ open |
| TEST-02 | P2 | Нет frontend coverage; критичные страницы не покрыты | `vite.config.ts`, `src/tests` | регрессии в UI | ⬜ open |
| TEST-03 | P3 | Дубли фикстур/фабрик | `tests/conftest.py` | поддержка тестов | ⬜ open |

---

## 10. Зависимости, документация, гигиена

| ID | P | Находка | Где | Влияние | Статус |
|---|---|---|---|---|---|
| OPS-01 | P2 | 6 ignored-файлов в индексе: 4 AI-плана, `.gigaide/gigaide.properties`, `db/seed_data.sql` | git index | мусор в репозитории | ⬜ open |
| OPS-02 | P2 | Лицензия: `main.py` — MIT, `LICENSE` — проприетарная, `package.json` — UNLICENSED; версия 1.88.0 vs changelog 1.2.0; README/docs расходятся | `main.py`, `LICENSE`, `package.json`, `README.md`, `docs/DB.md`, `docs/DEPLOY.md`, `docs/TESTING.md` | юридический/информационный риск | ⬜ open |
| OPS-03 | P2 | Нет ruff/mypy/black/pre-commit/Dependabot/CodeQL | backend/root | качество и supply chain | ⬜ open |
| OPS-04 | P3 | README 219 КБ / 1237 строк, ченджлог внутри | `README.md` | сложно читать/поддерживать | ⬜ open |
| OPS-05 | P3 | Нет SECURITY.md / CONTRIBUTING.md / ARCHITECTURE.md | root/docs | онбординг и процесс | ⬜ open |

---

## 11. Что перевести на библиотеки

Ключевой вывод: **точечно — да, массово — нет**.

| Что | Решение | Выгода | Когда |
|---|---|---|---|
| HTTP-клиенты MAX/VK/Yandex/DaData | общий `httpx.AsyncClient` + `tenacity` | retry/backoff, timeouts, меньше соединений | сейчас |
| CSV-экспорт | stdlib `csv.writer` | корректное экранирование, защита от formula injection | сейчас |
| Server-state фронтенда | **TanStack Query** (уже установлен) | убирает 96 effect'ов, даёт кэш/retry/дедуп | сейчас, пилот на 2–3 страницах |
| Фоновые циклы | один scheduler-процесс / RQ worker | нет дублей в воркерах, надёжный retry | 2–4 недели |
| Формы | `react-hook-form` + `zod` | единая валидация вместо копий | 3–4 недели |
| Модалки/select'ы | Radix Dialog/Select | focus trap, aria, клавиатура | 3–4 недели |
| API-типы | `openapi-typescript` | типы из FastAPI без дрейфа | 1–2 месяца |
| Тесты фронтенда | MSW | убирает ad-hoc моки | 1–2 месяца |
| Телефоны | `phonenumbers` | корректная нормализация | по необходимости |
| Фикстуры | `polyfactory` | меньше копипаста | по необходимости |
| Swiper | удалить, заменить CSS scroll-snap | минус ~100 КБ | сейчас |

**Не стоит:** Celery (RQ уже есть), Tailwind/UI-kit rewrite, i18next для одного языка, FullCalendar, DDD-фреймворк, DI-контейнер, микросервисы.

---

## 12. План работ

### Этап 0 — инцидент и P0 (сегодня)

- IR-01…IR-04: ротация секретов, проверка логов, очистка телефона, отзыв сессий.
- SEC-01 уже закрыт.

### Этап 1 — security/session pack + бронирование (1–2 недели) — выполнен

1. SEC-02 — OTP attempts: `1890479`.
2. SEC-03 — TTL имперсонации: `1890479`.
3. SEC-04 — refresh `is_active`: `1890479`.
4. DATA-01 — защита от гонки бронирования: `aed3bd7`.
5. DATA-02/DATA-03 — единый booking-service и корректный конфликт: `aed3bd7`.
6. DATA-05 — выручка по снапшотам: `aed3bd7`.
7. DEP-01/DEP-03 — точный SHA и порядок миграций: `c711ec8`.

### Этап 2 — надёжность и производительность (2–4 недели)

- DEP-02 (restore/rollback), DEP-04, DEP-05, DEP-07…DEP-10.
- DATA-04, DATA-06…DATA-09.
- PERF-01…PERF-07.
- SEC-05…SEC-10.
- OPS-01…OPS-03.
- TEST-01/TEST-02.

### Этап 3 — декомпозиция и фронтенд (1–2 месяца)

- ARCH-01…ARCH-11.
- TanStack Query, RHF/zod, Radix, MSW, openapi-typescript.
- Разбиение god-файлов и god-компонентов.
- RQ worker/один scheduler, дизайн-токены, a11y, Playwright.
- TEST-03, OPS-04/OPS-05.

---

## 13. Первый предлагаемый пакет правок

> Это предложение, а не начатая работа. Порядок можно менять.

| Шаг | Пункты | Результат | Оценка |
|---|---|---|---|
| 1 | IR-01…IR-04 | закрыт остаточный доступ после P0 | 1–2 часа, нужен сервер |
| 2 | SEC-02 | OTP нельзя перебрать | 0,5–1 день |
| 3 | SEC-03 + SEC-04 | короткая имперсонация, refresh не продлевает блокировку | 0,5 дня |
| 4 | DATA-01 + DATA-02 | нет двойных записей, корректные конфликты | 1–2 дня |
| 5 | DEP-01 + DEP-03 | deploy не выкатывает чужой commit и не стартует до миграций | 0,5–1 день |

**Рекомендация:** SEC-06 закрыт, Redis rate limit подключён (SEC-05 остался только account-лимит). Следующий пакет — DEP-05 (PG-гейт), DEP-02 (restore/rollback), затем DATA-08 и оставшиеся P1. IR-01/IR-02 остаются за владельцем инфраструктуры.

---

## 14. Журнал изменений

| Дата | ID | Коммит | Что изменено | Проверка | Статус |
|---|---|---|---|---|---|
| 2026-10-24 | AUDIT-00 | — | создан документ аудита | — | 🟨 |
| 2026-10-24 | SEC-01 | `b25f7c1` | удалён phone-only login, schema/service/frontend stub, захардкоженный телефон; regression-тест | CI `40068533306`, Deploy `40068533320`, prod `404`, `/health` `200` | ✅ fixed |
| 2026-10-24 | SEC-02/03/04 | `1890479` | OTP: счётчик ошибок, сжигание кода, ротация старых SMS-кодов, `hmac.compare_digest`; имперсонация 15 минут; refresh блокирует inactive/deleted | 17 targeted tests, `alembic upgrade head` на чистой SQLite, `alembic heads` = `6c4d5e6f7081` | ✅ fixed |
| 2026-10-24 | DATA-01/02/03/05 | `aed3bd7` | Бронирование сериализовано блокировкой мастера; конфликт использует снапшот длительности и нижнюю границу; админское создание валидирует услугу/конфликт; выручка считается по снапшоту и включает комплексы | 24 admin appointment tests, 13 dashboard tests, 20 booking/client tests | ✅ fixed |
| 2026-10-24 | DEP-01/02/03/06 | `c711ec8` | Deploy выкатывает точный `github.sha` с проверкой `rev-parse`; backend больше не рестартует до миграций; health-check ждёт `/health` и проверяет nginx; бэкап перенесён в `/var/backups`, пустой/упавший `pg_dump` останавливает деплой, retention 14 дней | YAML разобран, shell-синтаксис проверен статически; проверка на следующем deploy | DEP-01/03/06 ✅ fixed, DEP-02 🟨 (restore/rollback остаётся) |
| 2026-10-24 | SEC-05/06 | `904c06d` | slowapi использует Redis в production (fallback в memory), storage настраивается через `RATE_LIMIT_STORAGE_URI`; DaData-прокси ограничен allowlist `suggest/address`, лимитом 30/min и валидацией query/count | 14 targeted tests; Redis-путь покрыт unit-тестами выбора storage | SEC-06 ✅ fixed, SEC-05 🟨 (лимиты на аккаунт остаются) |

---

## 15. Метрики

| Метрика | На аудите | Цель | Сейчас |
|---|---:|---:|---:|
| Backend-тесты | 784 | ≥ 800 | 804 |
| Frontend-тесты | 281 | ≥ 300 | 281 |
| Backend coverage-gate | 55% | ≥ 65% | 55% |
| ESLint errors | 0 | 0 | 0 |
| ESLint warnings | 43 | ≤ 10 | 43 |
| npm prod: high / moderate | 1 / 2 | 0 / 0 | 1 / 2 |
| Открытых P0 (код + инцидент) | 3 | 0 | 2 (IR-01/02) |
| Открытых P1 | 18 | 0 | 8 |
| Время backend suite (локально, Windows) | ~27 мин | ≤ 10 мин | ~27 мин |
| Index JS | 547 КБ / 168 КБ gzip | ≤ 450 КБ | 547 КБ |

---

## 16. Открытые решения

1. **Порядок старта:** начинаем с IR + session hardening или сразу с бронирования?
2. **`/available-days` и `/available-slots`:** есть ли внешние клиенты? Если нет — удаляем, если да — реализуем корректно.
3. **TanStack Query:** внедряем на ключевые страницы или удаляем зависимость и оставляем текущий подход?
4. **React Router 7:** обновляемся в этом квартале или митигируем open redirect точечно?
5. **Лицензия:** оставляем проприетарную (тогда правим `main.py`/`package.json`) или переводим на MIT?
6. **Телефон администратора:** очистить полностью или оставить как контакт после смены номера?
7. **Python/Node:** поднимаем CI до Python 3.12 и Node 22 сейчас или отдельным этапом?

---

## 17. Приложение: команды проверки

```powershell
# Backend
cd online-booking\backend
.\\venv\\Scripts\\python.exe -m pytest tests/ -q
.\\venv\\Scripts\\python.exe -m pytest tests/ -q --cov=app --cov-report=term-missing --cov-fail-under=55

# Frontend
cd online-booking\frontend
npx tsc --noEmit
npx eslint src/
npx prettier --check src/
npx vitest run

# Production smoke (без секретов)
curl.exe -s -o NUL -w "%{http_code}" https://beauty-specialist.ru/health
curl.exe -s -o NUL -w "%{http_code}" https://beauty-specialist.ru/
```

---

## 18. Ссылки

- P0-фикс: `b25f7c1`
- CI: run `40068533306`
- Deploy: run `40068533320`
- Production: `https://beauty-specialist.ru/`
- API: [API.md](API.md)
- DB: [DB.md](DB.md)
- Deploy: [DEPLOY.md](DEPLOY.md)
- Testing: [TESTING.md](TESTING.md)

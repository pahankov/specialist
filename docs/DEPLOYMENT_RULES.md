# Deployment Rules & Anti-Patterns

> Все ошибки, допущенные при деплое beauty-specialist.ru, и как их избежать.

---

## 1. `script_stop: true` убивает деплой от любой мелочи

**Проблема:** `script_stop: true` включает `set -e` — скрипт прерывается от любой ошибки. Это включает:
- SIGPIPE от `head`/`tail` в pipe (`curl | head -c 200` — `head` закрывает pipe, `curl` падает с exit 141)
- `grep` без совпадений (exit 1)
- `ss | grep` — если порт не слушается, grep возвращает 1
- Любая команда с `|| true` внутри pipe может не сработать из-за `pipefail`

**Решение:** `script_stop: false`. Критические ошибки имеют явную проверку с `exit 1`. Неритические команды (curl, grep, ss) не должны рвать скрипт.

```yaml
# BAD — скрипт умрёт от любой мелочи
script_stop: true

# GOOD — скрипт продолжит, критические ошибки проверены явно
script_stop: false
```

---

## 2. SIGPIPE от `head` / `tail` в pipe

**Проблема:** `curl ... | head -c 200` — `head` читает 200 байт, закрывает pipe, `curl` получает SIGPIPE и падает.

**Решение:** Убрать pipe с `head`/`tail` или обернуть в `|| true`.

```bash
# BAD — SIGPIPE, exit 141
curl -sf http://.../countries/ | head -c 200

# GOOD — вывод игнорируется явно
curl -sf http://.../countries/ > /dev/null && echo "OK" || echo "FAILED"

# GOOD — pipe в подshell с || true
(systemctl status service | head -10) || true
```

---

## 3. Относительные пути после `cd`

**Проблема:** После `cd ../frontend` все относительные пути считаются от новой директории.

**Решение:** Использовать абсолютные пути для файлов, которые не в текущей директории.

```bash
# BAD — скрипт в scripts/, а мы в frontend/
bash deploy_fix_nginx.sh  # FileNotFoundError

# GOOD — абсолютный путь
bash /var/www/beauty-specialist/scripts/deploy_fix_nginx.sh
```

---

## 4. `git pull` не удаляет новые файлы и не чистит удалённые

**Проблема:** `git pull` не удаляет файлы, которых нет в репозитории, и не подтягивает удалённые.

**Решение:** Использовать `git fetch + git reset --hard + git clean -fd`.

```bash
# BAD — старые файлы остаются
git pull origin main

# GOOD — полная синхронизация
git fetch origin main
git reset --hard origin/main
git clean -fd
```

---

## 5. `GRANT ALL PRIVILEGES` ≠ смена владельца таблицы

**Проблема:** `GRANT ALL PRIVILEGES TO specialist` не меняет владельца таблицы. Если таблица создана `postgres`, а миграции запускает `specialist`, `ALTER TABLE` падает.

**Решение:** `ALTER TABLE ... OWNER TO specialist`.

```sql
-- BAD — grant не меняет владельца
GRANT ALL PRIVILEGES ON TABLE audit_logs TO specialist;

-- GOOD — меняет владельца
ALTER TABLE audit_logs OWNER TO specialist;
```

---

## 6. `Column(Time)` требует `datetime.time`, не строки

**Проблема:** `start_time="09:00:00"` — строка. asyncpg требует `datetime.time` объект.

**Решение:** Всегда использовать `time(9, 0)` для `Column(Time)`.

```python
# BAD — строка, падает с "str has no attribute hour"
WorkingHour(start_time="09:00:00", end_time="18:00:00")

# GOOD — datetime.time объекты
from datetime import time
WorkingHour(start_time=time(9, 0), end_time=time(18, 0))
```

---

## 7. `cat > /etc/...` требует root

**Проблема:** `cat > /etc/nginx/...` падает с `Permission denied` при запуске от `deploy`.

**Решение:** `sudo tee` вместо `cat >`.

```bash
# BAD — Permission denied
cat > /etc/nginx/sites-enabled/app << 'EOF'
...
EOF

# GOOD — sudo tee
sudo tee /etc/nginx/sites-enabled/app > /dev/null << 'EOF'
...
EOF
```

---

## 8. Windows CRLF ломает bash на Linux

**Проблема:** Файлы с `\r\n` падают с `command not found` на `\r`.

**Решение:** `sed -i 's/\r$//'` перед выполнением.

```bash
sed -i 's/\r$//' scripts/deploy_fix_nginx.sh
bash scripts/deploy_fix_nginx.sh
```

---

## 9. `git log -1` обрезан в выводе

**Проблема:** Вывод GitHub Actions обрезается, `Process exited with status 1` может быть скрыт.

**Решение:** Всегда проверять **последнюю строку** вывода на `Process exited with status N`. Если N ≠ 0 — деплой упал, даже если промежуточные шаги успешны.

---

## 10. `fix_all_tables.sql` падает на несуществующих колонках

**Проблема:** `ALTER TABLE ... ADD COLUMN name` падает, если колонка уже есть.

**Решение:** Использовать `DO $$ BEGIN ... END $$;` или `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (PostgreSQL 9.6+).

```sql
-- BAD — падает если колонка есть
ALTER TABLE cities ADD COLUMN name VARCHAR(100);

-- GOOD — безопасно
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='cities' AND column_name='name'
    ) THEN
        ALTER TABLE cities ADD COLUMN name VARCHAR(100);
    END IF;
END $$;
```

---

## 11. `is_available` нет в модели — но передается в конструктор

**Проблема:** `MasterProfile(is_available=True)` — аргумента нет в модели.

**Решение:** Перед созданием объекта проверить модель.

```python
# BAD — TypeError: 'is_available' is an invalid keyword
MasterProfile(user_id=1, is_available=True)

# GOOD — только поля модели
MasterProfile(user_id=1)
```

---

## 12. Отступы в Python — не просто стиль, а логика

**Проблема:** Лишние 4 пробела ломают блок кода. `if not user:` с отступом `if` внутри `else` — логика сломана.

**Решение:** Проверять отступы при ревью. Использовать `flake8`/`ruff` в CI.

---

## 13. Секреты в скриптах деплоя — только из env

**Проблема:** `create_superuser.py` и `fix_production_db.py` хранили пароль в коде. Чистка истории (`filter-repo`) заменила его плейсхолдером — и каждый деплой молча перезаписывал прод-пароль плейсхолдером. Симптом: вход по боевому паролю внезапно даёт 401 после зелёного деплоя.

**Решение:**
```python
# BAD — захардкожено, переживёт scrub только как плейсхолдер
SUPERUSER_PASSWORD = "REDACTED_SUPERUSER_PASSWORD"

# GOOD — env с keep-on-absent
password = os.getenv("SUPERUSER_PASSWORD") or None
if user_exists and not password:
    keep_hash()  # рутинный деплой ничего не трогает
```
Плюс: маскированные логи (пароль/хеш никогда в CI-вывод), fail-fast только когда создать без пароля невозможно. Проверять grep'ом: `git grep -n "REDACTED_" -- '*.py'` должен быть пуст.

---

## 14. Integrity-чеки сборки должны соответствовать архитектуре

**Проблема:** Чек `grep -q "/api/v1/cities" dist/ → exit 1` (“старого эндпоинта быть не должно”) стал ложным после того, как `/api/v1/cities` стал осознанным фолбэком DaData — деплой падал на зелёной сборке.

**Решение:** Проверять инварианты текущей архитектуры, а не вчерашней:
```bash
# DaData: прямых вызовов быть не должно (секрет не в бандле), прокси-путь обязан быть
grep -q "suggestions.dadata.ru" dist/assets/*.js && exit 1
grep -q "/api/dadata" dist/assets/*.js || exit 1
```
Перед пушем проверять чек локальной прод-сборкой (`npm run build` + те же grep).

---

## 15. Миграции проверять на слепке прод-состояния, а не на пустой БД

**Проблема:** После squash (12 файлов → `5280b944554f_baseline_full_schema`) deploy упал с
`Can't locate revision identified by 'b2c3d4e5f6a7'`. Причина: `alembic stamp X`
сначала резолвит **текущую** версию БД в каталоге миграций, а старых файлов там уже
нет. Локальная проверка на пустой БД (`upgrade head` с нуля) была зелёной и ничего
не показала — ошибка проявляется только когда в `alembic_version` лежит старый head.

**Решение:**
```bash
# Эмулируй прод: проставь старый head вручную и прогони ровно те команды, что в deploy
UPDATE alembic_version SET version_num='b2c3d4e5f6a7';
alembic stamp <new_baseline>   # <-- вот здесь и упало бы локально
alembic upgrade head
```
Правило: любая операция со штамповкой/переписыванием истории миграций тестируется
на БД, где в `alembic_version` лежит прод-значение. Пустая БД для таких проверок
не годится. Рабочая последовательность после squash: `DELETE FROM alembic_version`
→ `alembic stamp <baseline>` → `alembic upgrade head` (см. deploy.yml, блок ALEMBIC).

---

## Checklist перед деплоем

- [ ] `script_stop: false` (или все команды с `|| true`)
- [ ] Нет `| head` в pipe без `|| true`
- [ ] Нет `| tail` в pipe без `|| true`
- [ ] Абсолютные пути для файлов вне текущей директории
- [ ] `git reset --hard` вместо `git pull`
- [ ] `sudo tee` вместо `cat > /etc/...`
- [ ] `sed -i 's/\r$//'` для shell-скриптов
- [ ] `datetime.time` для `Column(Time)`, не строки
- [ ] `ALTER TABLE ... OWNER TO` вместо `GRANT`
- [ ] `IF NOT EXISTS` для `ALTER TABLE ADD COLUMN`
- [ ] Проверить модель перед передачей аргументов в конструктор
- [ ] Проверить отступы в Python
- [ ] Проверить **последнюю строку** вывода на `Process exited with status 0`
- [ ] Скрипты деплоя читают секреты только из env (`git grep -n "REDACTED_" -- '*.py'` пуст)
- [ ] Integrity-чеки сборки соответствуют текущей архитектуре (проверены локальным `npm run build`)
- [ ] Миграции со штамповкой проверены на слепке прод-`alembic_version`, а не на пустой БД (см. правило 15)

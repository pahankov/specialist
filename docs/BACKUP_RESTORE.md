# Бэкап и восстановление БД

Деплой делает `pg_dump` **до** миграций и останавливается, если дамп не создан
или получился пустым. Бэкапы лежат вне `/tmp` и переживают перезагрузку.

## Где лежат бэкапы

- Каталог: `/var/backups/beauty-specialist/`
- Имя: `db-YYYYMMDD-HHMMSS.sql`
- Retention: 14 дней (старые файлы удаляются на каждом деплое)
- Формат: plain SQL (`pg_dump` без `-Fc`), восстанавливается через `psql`

Проверить:

```bash
sudo ls -lh /var/backups/beauty-specialist/
sudo test -s /var/backups/beauty-specialist/db-YYYYMMDD-HHMMSS.sql
```

## Восстановление (сначала в отдельную БД)

Никогда не восстанавливайте поверх рабочей БД без проверки. Сначала поднимите
копию в отдельной базе и убедитесь, что данные читаются.

```bash
BACKUP=/var/backups/beauty-specialist/db-YYYYMMDD-HHMMSS.sql
RESTORE_DB=online_booking_restore

# 1. Проверить дамп
sudo test -s "$BACKUP"

# 2. Создать пустую БД
sudo -u postgres createdb "$RESTORE_DB"

# 3. Залить дамп
sudo -u postgres psql -v ON_ERROR_STOP=1 -d "$RESTORE_DB" -f "$BACKUP"

# 4. Проверить ключевые таблицы
sudo -u postgres psql -d "$RESTORE_DB" -c "SELECT count(*) FROM users;"
sudo -u postgres psql -d "$RESTORE_DB" -c "SELECT count(*) FROM appointments;"
sudo -u postgres psql -d "$RESTORE_DB" -c "SELECT version_num FROM alembic_version;"
```

Если проверка успешна, переключение на восстановленную БД:

```bash
# Остановить backend, чтобы не было записи в старую БД
sudo systemctl stop beauty-backend

# Переименовать базы (имена зависят от DATABASE_URL)
sudo -u postgres psql -c 'ALTER DATABASE online_booking RENAME TO online_booking_broken;'
sudo -u postgres psql -c 'ALTER DATABASE online_booking_restore RENAME TO online_booking;'

sudo systemctl start beauty-backend
curl -fsS http://127.0.0.1:8000/health
```

Старую БД `online_booking_broken` удаляйте только после проверки.

## Откат кода

Деплой выкатывает точный `github.sha`, поэтому откат — это новый коммит,
который возвращает нужное состояние и проходит те же гейты:

```bash
git revert <bad-commit>
git push origin main
```

Не делайте `git reset --hard` на сервере вручную: следующий деплой всё равно
вернёт состояние из `main`, а ручные изменения на сервере будут потеряны.

Если миграция уже изменила схему и откат кода без отката БД невозможен:

1. Остановить backend.
2. Восстановить дамп, снятый перед проблемным деплоем (см. выше).
3. Выкатить revert-коммит.
4. Проверить `/health` и ключевые сценарии.

## Чего не делать

- Не запускайте `fix_all_tables.sql` в обычном деплое: он заморожен, содержит
  `DROP COLUMN` и предназначен только для ручного аварийного восстановления.
- Не храните бэкапы в `/tmp`: они исчезают при перезагрузке.
- Не восстанавливайте дамп поверх рабочей БД без промежуточной проверки.

## Периодическая проверка

Раз в квартал (или перед крупным релизом) восстановите последний дамп в
отдельную БД и выполните проверки выше. Бэкап, который ни разу не
восстанавливали, нельзя считать рабочим.

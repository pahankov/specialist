# Секреты: хранение, получение, добавление

> В этом файле — только правила. Никаких значений.

## Канон (единственное место, где живут секреты)

> Рантайм-канон — `online-booking/backend/.env` (gitignored).
> Человеческий реестр — `LOCAL.md` (gitignored, зеркалит значения из `backend/.env`).
> Больше `.env` нигде нет: корневой `.env` удалён осознанно (дублировал `backend/.env`
> и вводил в заблуждение). Фронт секретов не хранит — только same-origin `/api/...`.

| Где | Что | В git? |
|---|---|---|
| `online-booking/backend/.env` | ЕДИНСТВЕННЫЙ рантайм-файл: БД, JWT, Redis, SMS, DaData, OAuth, `SUPERUSER_*`, `PROD_*`, `MAX_*` | НЕТ (gitignored) |
| `LOCAL.md` (корень) | Человекочитаемое зеркало значений + SSH/серверные пароли (не для рантайма) | НЕТ (gitignored) |
| GitHub Secrets | `SERVER_HOST`, `SERVER_SSH_KEY`, `DATABASE_URL` — только для деплоя | НЕТ (показывает `***`) |
| `/var/www/beauty-specialist/online-booking/backend/.env` | Прод-канон (читает deploy workflow) | НЕТ (только на сервере) |
| `.env.example` (корень) | Шаблон с пустыми/фейковыми значениями | ДА |

Правило: секрет, которого нет в `LOCAL.md`, — потерян. Секрет, попавший в код, логи или чат, — скомпрометирован (чистить через `filter-repo`, см. `docs/RULES.md`).

## Как достать, когда понадобилось

1. **Локально** — открой `LOCAL.md` или `online-booking/backend/.env`.
2. **Прод-значения** — по SSH: `cat /var/www/beauty-specialist/online-booking/backend/.env` (или `grep KEY ...` для одного ключа). Копируй через буфер, не оставляй в файлах вне канона.
3. **Что использует деплой** — GitHub Secrets видны только как `***`. Посмотреть нельзя, можно только перезаписать новым значением. Маскировка `DATABASE_URL` в логах уже вшита в workflow.

## Как добавить новый секрет

1. Добавь ключ с пустым/фейковым значением в `.env.example`.
2. Прочитай его в бэкенде через `Settings` (`app/config.py`) — никаких `os.environ` напрямую и никаких дефолтных реальных значений.
3. Запиши реальное значение в `LOCAL.md` и в локальный `backend/.env`.
4. Если секрет нужен деплою — добавь в GitHub Secrets.
5. Если секрет нужен проду — добавь в серверный `.env` (по SSH, `nano ...`, затем `systemctl restart beauty-backend`).
6. Проверь: `git grep -i <ключ>` пуст, в бандле фронта секрета нет (фронт вообще не хранит секреты — только same-origin `/api/...`).

## Ротация (пример: ключ DaData)

1. Получи новый ключ в кабинете провайдера.
2. Обнови `LOCAL.md` + локальный `backend/.env` + серверный `.env`.
3. Перезапусти бэкенд (`systemctl restart beauty-backend`).
4. Проверь прод: `curl https://beauty-specialist.ru/api/v1/cities/search/?q=...`.
5. Старый ключ отзови в кабинете провайдера.

## MAX bot: серверная настройка (один раз)

```bash
# по SSH на сервере, из online-booking/backend (venv активен):
nano .env   # добавь MAX_BOT_TOKEN, MAX_BOT_USERNAME, MAX_BOT_URL, MAX_WEBHOOK_SECRET
python max_webhook.py status      # проверить текущую подписку
python max_webhook.py subscribe   # подписать https://beauty-specialist.ru/api/max/webhook
sudo systemctl restart beauty-backend
# проверка: отправь боту любое сообщение, в логах — "MAX webhook: update_type=..."
```

Токен, показанный в чате/на скриншоте, считается скомпрометированным:
перегенерируй его в настройках бота и обнови оба `.env` (локальный + серверный).

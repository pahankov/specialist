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
nano .env   # добавь MAX_BOT_TOKEN, MAX_BOT_USERNAME, MAX_BOT_URL, MAX_WEBHOOK_SECRET,
            # MAX_WEBHOOK_URL=https://beauty-specialist.ru/api/max/webhook
sudo systemctl restart beauty-backend
# проверка: в логах — "MAX webhook guard loop started" и "MAX webhook: update_type=..."
```

`MAX_WEBHOOK_URL` включает фоновый guard (`app/services/max_webhook_guard.py`):
при старте и раз в 10 минут он сверяет подписку и молча восстанавливает её.
Это защита от автоотписки MAX: если вебхук 8 часов не отвечал успешно, MAX сам
отписывает бота — без единой ошибки на сайте код в диалог перестаёт приходить.

Ручные команды (диагностика/dev, из `online-booking/backend`):

```bash
python max_webhook.py status      # текущие подписки
python max_webhook.py subscribe   # подписать вручную (URL из MAX_WEBHOOK_URL)
python max_webhook.py unsubscribe # снять подписку (dev / long-poll)
```

Токен, показанный в чате/на скриншоте, считается скомпрометированным:
перегенерируй его в настройках бота и обнови оба `.env` (локальный + серверный).

## Yandex suggest («Мгновенная авторизация»): настройка (один раз)

Виджет включён, пока задан `YANDEX_SUGGEST_REDIRECT_URI` (пусто = выключен,
работает прежняя кнопка-редирект). Перед включением:

1. В кабинете Яндекса (Платформы приложений → Веб-сервисы → Redirect URI)
   добавить URL страницы-приёмника **точно как есть**:
   - прод: `https://beauty-specialist.ru/suggest-token.html`
   - локалка: `http://localhost:3000/suggest-token.html`
2. Записать тот же URL в `backend/.env`:
   - прод (по SSH, затем `sudo systemctl restart beauty-backend`):
     `YANDEX_SUGGEST_REDIRECT_URI=https://beauty-specialist.ru/suggest-token.html`
   - локально: `YANDEX_SUGGEST_REDIRECT_URI=http://localhost:3000/suggest-token.html`
3. Проверка: в модалке входа вместо «Войти через Яндекс» рисуется официальная
   кнопка «Войти с Яндекс ID» (на вкладке регистрации — такая же официальная
   иконка-плитка).

Страница-приёмник — `frontend/public/suggest-token.html` (копируется в сборку
как есть, `sdk-suggest-token.js` отдаёт токен приложению через postMessage).
Откат — очистить `YANDEX_SUGGEST_REDIRECT_URI`: фронт сам вернётся на
кнопку-редирект.

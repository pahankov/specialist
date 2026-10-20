# API Reference — Online Booking

> Таблицы эндпоинтов и curl-кукбук. Вынесено из README для компактности.
> Base URL (local): `http://localhost:8000`. Интерактивная документация: `/docs`.

## 🔌 API Endpoints

### Auth
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/register` | Legacy-регистрация мастера (пароль не используется для входа — мастера входят только через соцсети) |
| `POST` | `/api/v1/auth/login` | Вход по email + паролю для клиентов/администратора; мастеру — 403 «только VK/Яндекс/MAX» (JWT + refresh token в cookies) |
| `POST` | `/api/v1/auth/login-unified` | Вход по email ИЛИ телефону (клиенты/админ; мастеру по паролю — 403, соцвходы остаются; пишет login в аудит) |
| `POST` | `/api/v1/auth/register-unified` | Быстрая регистрация: только `phone` + `password` + `consent` (152-ФЗ) — всегда CLIENT, сразу входит: access_token + cookies; email/имя/адрес заполняются позже в кабинете. Без `consent` — 400 (согласие обязательно) |
| `GET` | `/api/v1/auth/become-master` | Черновик профиля мастера: данные формы, контакты, привязки и чек-лист готовности; для активного мастера — `status=active` |
| `PATCH` | `/api/v1/auth/become-master` | Сохранить черновик профиля мастера (неполный можно); кабинет остаётся неактивным, роль — CLIENT |
| `POST` | `/api/v1/auth/become-master/activate` | Сохранить форму и сразу активировать кабинет: проверяет имя+фамилию, адрес, телефон, подтверждённую почту и соцпривязку; меняет роль на MASTER и выдаёт новую access-cookie |
| `POST` | `/api/v1/auth/become-master/photo` | Фото/сертификат черновика до активации (JPEG/PNG/WebP, до 5 МБ) |
| `POST` | `/api/v1/auth/send-otp` | Отправка SMS-кода клиенту |
| `POST` | `/api/v1/auth/verify-otp` | Проверка кода, вход/регистрация клиента |
| `POST` | `/api/v1/auth/phone/status` | Единый вход: чем ответить на телефон — `new` (аккаунта нет → регистрация), `password` (есть пароль → в фокус), `social` (только соцвход/MAX → кнопки); для `new` возвращает `challenge` (JWT, TTL 5 мин) для 2-шагового флоу согласия (152-ФЗ); сам не входит и ничего не создаёт |
| `POST` | `/api/v1/auth/consent/complete` | Завершение 2-шагового согласия (OAuth verify): `challenge` + `consent=true` → стемпит `consent_at` и версии документов, создаёт профиль клиента и welcome-уведомление, возвращает JWT-сессию + cookies; `consent=false` → 400; 10/min |
| `POST` | `/api/v1/auth/password/change` | Смена пароля клиента/администратора: `current_password` + `new_password`; мастеру — 400 (только соцвходы); 10/min |
| `POST` | `/api/v1/auth/password/forgot` | «Забыли пароль»: код на почту; мастеру код не отправляется; ответ одинаков для известной и неизвестной почты (без энумерации); 5/min |
| `POST` | `/api/v1/auth/password/reset` | Новый пароль по коду из письма + авто-вход: access_token + cookies; мастеру — 400; успех подтверждает почту (`verified_via="code"`), все прежние сессии отзываются; 10/min |
| `POST` | `/api/v1/auth/refresh` | Обновление access token (refresh token rotation) |
| `POST` | `/api/v1/auth/logout` | Выход (очистка cookies) |
| `POST` | `/api/v1/auth/client/login` | Legacy вход клиента по телефону |

### MAX chat-bot auth (SMS-style; бот @se14458556_bot)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/max/start` | Заявка на код: `deeplink` (один клик, автовстреча), `delivered` (push в известный диалог), иначе — share-number flow; 10/min |
| `POST` | `/api/v1/auth/max/verify` | Проверка кода с сайта, JWT-сессия + cookies (10/min); для нового аккаунта без согласия — `challenge` вместо сессии (152-ФЗ) |
| `POST` | `/api/max/webhook` | Приём MAX Bot API updates (`message_created`, `bot_started`; секрет `X-Max-Bot-Api-Secret`) |

Флоу: сайт берёт телефон → юзер делится номером с ботом (текст или кнопка
`request_contact`) → бот присылает код в диалог (+ кнопка «Скопировать код») →
юзер вводит код на сайте. Номер из `request_contact` с верным HMAC — доказанно
привязан к MAX-аккаунту (`is_verified=True`); набранный текстом — нет
(`is_verified=False`, как в SMS-флоу). Имя из MAX — дефолт нового клиента.
Роль берётся из существующего юзера: мастер/админ входит по номеру своего
аккаунта (новый юзер всегда CLIENT; стать мастером — заполнить и сразу
активировать черновик в `/cabinet/become-master`).

Ответ боту отправляется фоном (`BackgroundTasks`): вебхук отвечает MAX `200`
сразу после записи в БД, а сообщение в диалог уходит следом. Подписка
самовосстанавливается guard-циклом (`max_webhook_guard.py`; включается
`MAX_WEBHOOK_URL`, проверка при старте и раз в 10 минут) — MAX автоотписывает
бота, если вебхук 8 часов не отвечал успешно.

**Challenge token (1.80.0):** для нового аккаунта без согласия `/max/verify`
возвращает `challenge` (JWT с `sub`, `phone`, `iat`, TTL 5 мин) вместо JWT-сессии
и не ставит cookies. Фронт показывает `ConsentScreen` → пользователь принимает
согласие → `POST /auth/consent/complete` {`challenge`, `consent: true`} → бэкенд
стемпит `consent_at`, создаёт профиль клиента и welcome-уведомление, возвращает
JWT-сессию. То же — для существующего аккаунта без `consent_at` (брошенная
регистрация): молчаливого входа нет, согласие спрашивается снова.

### VK ID auth (виджет VK + Одноклассники + Mail; OAuth 2.0 + PKCE)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/vk/start` | Подписанный `state` (HMAC, TTL 10 мин) + `redirect_uri` + `client_id` + полный `authorize_url` по `code_challenge` (браузерный PKCE); 10/min |
| `POST` | `/api/v1/auth/vk/verify` | Обмен `code`+`device_id`+`state`+`code_verifier` на токены **на сервере** (сервисный ключ не уходит в браузер), create/bind аккаунта, JWT-сессия + cookies; для нового аккаунта без согласия — `challenge` вместо сессии (152-ФЗ); 10/min |

Флоу (официальный виджет `@vkid/sdk`, блок OAuthList с кнопками VK/OK/Mail):
фронт генерирует PKCE `code_verifier` и шлёт только его SHA-256 (`code_challenge`)
в `/vk/start` → получает подписанный `state` + `redirect_uri` + `client_id` →
передаёт **свой** `state` и `code_verifier` в `Config.init` (`responseMode=Callback`)
→ рисует виджет. После одобрения внутри VK срабатывает
`LOGIN_SUCCESS` (`code` + `device_id`) → фронт постит их + `state` + `code_verifier`
+ `consent` в `/vk/verify` → бэкенд меняет `code` на токены у
`id.vk.ru/oauth2/auth`, читает профиль (`/oauth2/user_info`), создаёт/привязывает
аккаунт (новый всегда CLIENT) и штампует `consent_*`. Токены VK в браузер не
попадают; `state`, переданный в SDK, проходит HMAC-проверку на бэке — ручной
редирект на `id.vk.ru` больше не используется.

**Challenge token (1.80.0):** для нового аккаунта без согласия `/vk/verify`
возвращает `challenge` (JWT с `sub=user_id`, `phone`, `iat`, TTL 5 мин) вместо
JWT-сессии и не ставит cookies. Фронт показывает `ConsentScreen` (ссылки на
оферту и политику) → пользователь принимает → `POST /auth/consent/complete`
{`challenge`, `consent: true`} → бэкенд стемпит `consent_at`, создаёт профиль
клиента и welcome-уведомление, возвращает JWT-сессию. Аккаунт без `consent_at`
(в т.ч. брошенная регистрация) снова получает `challenge` — молчаливого входа
нет. Фронт всегда шлёт `consent=false` и решает по ответу: `challenge` или
готовые cookies.

### Yandex ID auth (официальный виджет suggest + Authorization Code, редирект-фолбэк)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/v1/auth/yandex/start` | Подписанный `state` (HMAC, TTL 10 мин) + `redirect_uri` + `client_id` + `suggest_redirect_uri` (страница-приёмник виджета; пусто = виджет выключен) + полный `authorize_url` на `oauth.yandex.ru/authorize`; 10/min |
| `POST` | `/api/v1/auth/yandex/verify` | Либо обмен `code`+`state` на токены **на сервере** (OAuth-секрет не уходит в браузер), либо проверка `access_token` виджета (`login.yandex.ru/info`); create/bind аккаунта, JWT-сессия + cookies; для нового аккаунта без согласия — `challenge`; ровно один способ, иначе 422; 10/min |

Два флоу, у обоих один хвост (create/bind аккаунта, новый всегда CLIENT,
ключ — `yandex_user_id`, штамп `consent_*`):

- **Виджет «Мгновенная авторизация»** (основной, `sdk-suggest.js`): фронт
  монтирует официальную кнопку/иконку (`YaAuthSuggest.init` с `client_id` и
  `suggest_redirect_uri` из `/yandex/start`), после согласия пользователя SDK
  получает OAuth-токен через страницу-приёмник `frontend/public/suggest-token.html`
  и отдаёт его промису; фронт постит `access_token`+`consent` в `/yandex/verify`
  → бэкенд валидирует токен чтением профиля (`login.yandex.ru/info`) и логинит.
  Дальше токен в браузере не используется. Если SDK не может работать (нет
  сторонних cookie, нет конфига, CDN недоступен) — фронт сам рендерит кнопку
  редирект-флоу ниже.
- **Редирект** (фолбэк, без PKCE — подтверждает `client_secret`): фронт шлёт
  `/yandex/start` → получает подписанный `state` + `authorize_url` → стешит
  `state` в sessionStorage и редиректит браузер на Яндекс → Яндекс возвращает
  на `/auth/yandex/callback?code&state` → фронт сверяет `state` со стешенным
  и постит `code`+`state` в `/yandex/verify` → бэкенд меняет `code` на токен
  у `oauth.yandex.ru/token` (серверный `client_secret`). `state` проходит
  HMAC-проверку на бэке.

**Challenge token (1.80.0):** как у VK — новый аккаунт без согласия получает
`challenge` вместо сессии; `ConsentScreen` показывается и в виджете, и на
callback-странице редирект-флоу, дальше — `/auth/consent/complete`.

### Geography
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/countries/` | Список стран |
| `GET` | `/api/v1/countries/{country_id}` | Страна по ID |
| `GET` | `/api/v1/cities/` | Список городов (пагинация, поиск, фильтр по стране) |
| `GET` | `/api/v1/cities/search/?q=&limit=` | Поиск городов для автокомплита (фолбэк DaData) |
| `GET` | `/api/v1/cities/{id}` | Город по ID |
| `POST` | `/api/v1/cities/resolve` | Get-or-create города по имени (сначала ищет семью дублей DaData; любой авторизованный пользователь) |
| `POST` | `/api/v1/cities/merge-duplicates` | Супер: слить города-дубли (dry-run; `?apply=true` — оставить старший id, перепривязать юзеров) |

### DaData (backend proxy, секрет не покидает сервер)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `POST` | `/api/dadata/{path}` | Прокси в DaData 4_1/rs: форвардит тело, зеркалит статус (503 — нет ключей, 502 — апстрим недоступен) |

### Masters
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/masters/?city_id=` | Активные мастера (+`city_id/city_name/avg_rating/avatar_preset` в ответе; фильтр по семье города-дублей) |
| `GET` | `/api/v1/masters/{id}` | Мастер по ID |
| `POST` | `/api/v1/masters/` | Создать мастера — **legacy-ветка** (канонично: `/admin/masters`) |
| `PATCH` | `/api/v1/masters/{id}` | Обновить мастера — **legacy-ветка** |
| `DELETE` | `/api/v1/masters/{id}` | Удалить мастера — **legacy-ветка** |

> Legacy-ручки оставлены для совместимости; актуальные операции — в Admin/Superadmin (`/admin/masters...`). В новом коде не использовать.

### Services
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/services/?master_id=` | Список услуг (+`category` для группировки) |
| `GET` | `/api/v1/services/{id}` | Услуга по ID |
| `POST` | `/api/v1/services/` | Создать услугу — **legacy-ветка** (канонично: `/admin/services`) |
| `DELETE` | `/api/v1/services/{id}` | Удалить услугу — **legacy-ветка** |

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
| `GET` | `/api/v1/clients/` | Список клиентов — **legacy-ветка** |
| `GET` | `/api/v1/clients/{id}` | Клиент по ID — **legacy-ветка** |
| `POST` | `/api/v1/clients/` | Создать клиента — **legacy-ветка** |
| `DELETE` | `/api/v1/clients/{id}` | Удалить клиента — **legacy-ветка** |

> Клиентские данные канонично живут в кабинете (`/client/me`) и админ-панели (`/admin/clients`); legacy-ручки — только для совместимости.

### Cabinet (JWT CLIENT or MASTER — dual-role: masters book as clients)

> Inbox scoping for dual accounts: the cabinet shows only client-side bells
> (cancels, blocks, broadcasts from masters); booking bells from clients stay
> in the master panel. Badges use the same scope. Self-booking is rejected
> (400) and hidden from the wizard.
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/client/me` | Свой профиль (имя/фамилия/телефон/город/адрес + `contacts` и `has_password` для карточек профиля) |
| `PATCH` | `/api/v1/client/me` | Имя/фамилия/город/адрес (`city_id` проверяется, 404) |
| `POST` | `/api/v1/client/contacts` | Добавить свой телефон/почту (`contact_type` + `value`; занятое значение — 409, включая легаси-колонки) |
| `DELETE` | `/api/v1/client/contacts/{id}` | Удалить свой контакт (парольный аккаунт не может остаться без контактов — 400) |
| `POST` | `/api/v1/client/contacts/{id}/primary` | Сделать контакт основным (в своём типе: телефон/почта) |
| `GET` | `/api/v1/client/stats` | Дашборд: траты, визиты, предстоящие, любимые мастер/услуга |
| `GET` | `/api/v1/client/appointments` | Свои записи (все, новые сверху; фронт делит на будущие/историю) |
| `POST` | `/api/v1/client/appointments` | Своя запись из визарда (`master_id` + ровно один из `service_id`/`bundle_id` + date, проверка конфликтов по длительностям; статус `pending` или сразу `confirmed` при `auto_confirm` мастера; мастеру падает в колокольчик вместе с комментарием клиента) |
| `GET` | `/api/v1/client/bundles?master_id=` | Активные комплексы мастера (состав, время, цена; время = ручное или сумма) |
| `GET` | `/api/v1/client/booking/schedule` | Активное расписание мастера на месяц (окно + рабочие дни + занятые гранулы, без персональных данных) |
| `POST` | `/api/v1/client/appointments/{id}/cancel` | Отмена своей pending/confirmed записи (чужая — 404, финальная — 400; пишется в аудит) |
| `DELETE` | `/api/v1/client/me` | Удалить свой аккаунт (деактивация + обезличивание ПДн, отмена будущих записей; вход и токены умирают сразу, строки хранятся 3 года) |
| `GET` | `/api/v1/client/notifications/inbox`, `/api/v1/client/notifications/unread-count` | Входящие кабинета и бейдж колокольчика |
| `POST` | `/api/v1/client/notifications/{id}/read`, `/api/v1/client/notifications/read-all` | Отметить прочитанным |
| `DELETE` | `/api/v1/client/notifications` | Очистить уведомления кабинета |

### Working Hours
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/v1/working-hours/` | Расписание |
| `POST` | `/api/v1/working-hours/` | Добавить расписание |
| `DELETE` | `/api/v1/working-hours/{id}` | Удалить расписание |

### Admin (JWT required, master-scoped)
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/admin/dashboard` | Статистика (записи, клиенты, доход, `top_clients` топ-5 по тратам; `recent_appointments` — ближайшие живые) |
| `GET` | `/admin/monthly-stats` | Статистика за месяц (есть `cancelled_appointments`) |
| `GET` | `/admin/revenue-breakdown` | Детализация дохода (`by_master`/`by_service`, `date_from`/`date_to`; супер — `?master_id=`) |
| `GET` | `/admin/appointments` | Список записей (пагинация, фильтрация; `show_completed`/`show_cancelled` — пейджер считает показанное) |
| `POST` | `/admin/appointments` | Создать запись |
| `POST` | `/admin/appointments/book` | Админская запись (выбор клиента из БД; услуга ИЛИ комплекс; суперадмин шлёт `master_id`) |
| `GET` | `/admin/appointments/by-date` | Записи по дате (есть `service_id/service_duration` для спанов гранул) |
| `PATCH` | `/admin/appointments/{id}/confirm` | Подтвердить запись (клиенту падает в колокольчик) |
| `PATCH` | `/admin/appointments/{id}/cancel` | Отменить запись (клиенту падает в колокольчик с причиной) |
| `PATCH` | `/admin/appointments/{id}/complete` | Завершить запись |
| `PATCH` | `/admin/appointments/{id}/reopen` | Вернуть завершённую в работу (confirmed + колокол клиенту) |
| `DELETE` | `/admin/appointments/{id}` | Удалить запись |
| `GET` | `/admin/services` | Список активных услуг |
| `GET` | `/admin/services/all` | Все услуги (включая неактивные; суперадмин: `?master_id=`) |
| `POST` | `/admin/services` | Создать услугу (`discount_percent?` 0–90, `discount_fixed?` ₽, `discount_until?`) |
| `PATCH` | `/admin/services/{id}` | Обновить услугу (те же поля скидок) |
| `DELETE` | `/admin/services/{id}` | Soft-delete услуги |
| `GET` | `/admin/bundles` | Свои комплексы (состав, суммы времени/цены, своя цена); админ `?master_id=` — комплексы выбранного мастера |
| `POST` | `/admin/bundles` | Собрать комплекс (`name`, `service_ids` ≥2 своих услуг, `durations?` {id: мин}, `price?`, `duration_override?` — ручное время вместо суммы, `discount_percent?` 0–90, `discount_fixed?` ₽, `discount_until?`) |
| `PATCH` | `/admin/bundles/{id}` | Обновить комплекс (состав/время/цена/`is_active`; `price: null` — сброс к сумме; `duration_override: null` — сброс к сумме; `discount_percent` 0–90, `discount_fixed` ₽, `discount_until`) |
| `DELETE` | `/admin/bundles/{id}` | Удалить комплекс (прошлые записи хранят `bundle_name`) |
| `GET` | `/admin/clients` | Свои клиенты (мастер: с записями у него или созданные им; супер: все). Пагинация, `city_id`/`city_name`, `address` |
| `POST` | `/admin/clients` | Создать клиента (адрес одним полем + `city_name` для подбора; `city_id` тоже можно) |
| `PATCH` | `/admin/clients/{id}` | Обновить клиента (можно `city_id`) |
| `DELETE` | `/admin/clients/{id}` | Мастер: архив с причиной (`?reason=moved/left/inactive/deceased/other` + `?note=`). Админ: блок у всех мастеров. Админ `?purge=true`: необратимое стирание (только для требований о забвении, пишется в аудит) |
| `POST` | `/admin/clients/{id}/restore` | Вернуть из архива/снять блок (мастер — у себя, админ — `?master_id=` или везде) |
| `POST` | `/admin/clients/{id}/block` | Чёрный список: скрытие + запрет новой записи (кабинет 403, расписание 403, публичная форма 404; история анонимизирована; новая запись с любой стороны снимает блок). Причина блока выбирается на фронте (`?block_reason=no_show/rude/spam/debt/other` + `?note=`), админ видит кем/за что в `hidden_by`. Клиент получает колокольчик: отмена каждой будущей записи + объяснение блока (другой мастер или контакты из профиля). Мастер — за себя; админ — `?master_id=` за выбранного мастера, без него сразу у всех |
| `DELETE` | `/admin/clients/{id}/block` | Разблокировать (клиент полностью видим снова; scope как у block) |
| `POST` | `/admin/clients/{id}/toggle-active` | Выключатель аккаунта — только админ (мастера: архив/блок) |
| `POST` | `/admin/clients/bulk-city` | Назначить город всем по фильтру (`city_id` + `search`/`master_id`) |
| `GET` | `/admin/working-hours` | Расписание |
| `POST` | `/admin/working-hours` | Добавить рабочий день |
| `PATCH` | `/admin/working-hours/{id}` | Обновить рабочий день |
| `POST` | `/admin/working-hours/{id}/toggle-active` | Включить/выключить рабочий день (пересчитывает статус мастера) |
| `DELETE` | `/admin/working-hours/{id}` | Удалить рабочий день |
| `GET` | `/admin/work-window` | Окно рабочего времени мастера (`?master_id=` для суперадмина) |
| `PATCH` | `/admin/work-window` | Задать окно (`start_hour`/`end_hour`, 0–24) |
| `GET` | `/admin/profile` | Свой профиль (имя/фамилия/город/контакты/фото или пресет/адрес/сертификаты) |
| `PATCH` | `/admin/profile` | Свои данные: имя, фамилия, город, telegram, описание, опыт, адрес кабинета, сертификаты, `avatar_preset` (эмодзи из 16 стандартных; null — снять; заменяет загруженное фото) |
| `POST` | `/admin/profile/avatar` | Своё фото (JPEG/PNG/WebP, на входе ≤5МБ, иначе 400) → даунскейл до 1024px (JPEG/WebP q82, PNG optimize) → `avatar_url` на `/static` (снимает пресет). Файлы лежат на бэкенде — фронт резолвит через `assetUrl`. `?kind=cert` — отдельный файл (фото сертификата): не трогает аватар и ничего не удаляет |
| `DELETE` | `/admin/profile` | Удалить свой аккаунт мастера (снятие с публикации, обезличивание ПДн, отмена будущих записей клиентов; админам — 400) |
| `GET` | `/admin/audit-logs` | Журнал действий (пагинация, фильтрация; есть сущность `auth` — входы/выходы) |
| `GET` | `/admin/audit-logs/all` | Все логи системы (только супер: `entity_type`/`master_id`/`limit`/`offset`/`sort_dir`) |
| `GET` | `/admin/export/appointments` | Экспорт записей в CSV (`status`, `master_id`, `ids`, `include_master`) |
| `GET` | `/admin/export/clients` | Экспорт клиентов в CSV (`ids`, `search`, `master_id`; есть колонка Город) |
| `GET` | `/admin/export/clients/status/{job_id}` | Статус фонового экспорта клиентов |
| `GET` | `/admin/export/masters` | Экспорт мастеров в CSV (суперадмин; `ids`) |
| `GET` | `/admin/blocked-slots` | Заблокированные слоты |
| `POST` | `/admin/blocked-slots` | Заблокировать слот |
| `DELETE` | `/admin/blocked-slots/{id}` | Убрать блокировку |
| `GET` | `/admin/notifications/audience-counts` | Охват аудитории (`audience`, `user_ids`): всего получателей |
| `POST` | `/admin/notifications/broadcast` | Внутренняя рассылка в колокольчик (`audience`, `user_ids?`, `text` 1–4000). Супер: `all/masters/clients/selected`; мастер: `my_clients/selected` (только свои). Пишет по строке на получателя + строку в историю |
| `GET` | `/admin/notifications/sent` | Свои отправленные: что/когда/кому (текст, аудитория, получатели, дата) |
| `DELETE` | `/admin/notifications/sent` | Очистить историю отправленных (у получателей колокольчики остаются) |
| `GET` | `/admin/notifications/inbox` | Свои входящие (панели): `unread_only`, пагинация, счётчик `unread` |
| `GET` | `/admin/notifications/unread-count` | Бейдж колокольчика (панели) |
| `POST` | `/admin/notifications/{id}/read`, `/admin/notifications/read-all` | Отметить прочитанным |
| `DELETE` | `/admin/notifications` | Очистить свои входящие (панели) |

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
| `POST` | `/admin/bulk/toggle-active` | Массовая смена статуса (тело `{"master_ids": [...]}`) |
| `POST` | `/admin/bulk/suspend` | Массовая блокировка |
| `POST` | `/admin/bulk/unsuspend` | Массовая разблокировка |
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
| `GET` | `/api/v1/reviews/` | Публичный список отзывов (фильтр по `master_id`; `only_published` — по умолчанию только опубликованные, `false` — все) |
| `GET` | `/api/v1/reviews/average` | Средний рейтинг мастера (только опубликованные) |
| `POST` | `/api/v1/reviews/` | Legacy-создание отзыва (только на completed appointment); каноничные флоу — `/client/reviews` (клиент) и `/admin/reviews` (мастер/супер) |
| `PATCH` | `/api/v1/reviews/{id}` | Legacy: comment / publish-unpublish |
| `DELETE` | `/api/v1/reviews/{id}` | Legacy-удаление отзыва |
| `GET` | `/client/reviews/mine` | Свои отзывы кабинета (для пометок в Истории) |
| `POST` | `/client/reviews` | Оценить свой визит: completed или прошедший по времени (отменённые нельзя; 403 чужая, 409 повтор); мастеру летит ⭐-колокол |
| `GET` | `/client/coupons/mine` | Свои годные купоны (`?master_id=` — одного мастера): код, условия, срок, остаток |
| `POST` | `/client/coupons/preview` | Проверить промокод до записи (`master_id`, `service_id?`/`bundle_id?`, `code`) → новая цена или понятная ошибка |
| `POST` | `/admin/coupons` | Выдать купон своим (`kind` percent/fixed, `value`, `max_uses?`, `user_ids?` свои, `valid_until?`; код авто; колокол получателям) |
| `GET` | `/admin/coupons` | Свои купоны (использования, остатки) |
| `DELETE` | `/admin/coupons/{id}` | Выключить купон (история хранится) |

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
curl -X GET http://localhost:8000/api/v1/admin/masters

# Поиск мастеров
curl -X GET "http://localhost:8000/api/v1/admin/masters?search=Елена&is_active=true&is_admin=false"

# Создать мастера
curl -X POST http://localhost:8000/api/v1/admin/masters \
  -H "Content-Type: application/json" \
  -d '{"name":"Мария","email":"maria@example.com","password":"SecurePass456!","phone":"+79991234568"}'

# Блокировка мастера
curl -X POST http://localhost:8000/api/v1/admin/masters/1/toggle-active

# Назначение прав суперпользователя
curl -X POST http://localhost:8000/api/v1/admin/masters/1/toggle-admin

# Статистика по мастеру
curl -X GET http://localhost:8000/api/v1/admin/masters/1/stats
```

### Детализация дохода (суперпользователь)
```bash
curl -X GET "http://localhost:8000/api/v1/admin/revenue-breakdown?by_master=true" \
  -H "Authorization: Bearer <token>"
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
curl -X POST http://localhost:8000/api/v1/admin/bulk/toggle-active \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"master_ids": [1, 2, 3]}'

# Массовая блокировка
curl -X POST http://localhost:8000/api/v1/admin/bulk/suspend \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"master_ids": [1, 2, 3]}'
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
curl -X GET "http://localhost:8000/api/v1/admin/export/appointments?background=true&status=pending" \
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

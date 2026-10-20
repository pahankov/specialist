"""Online Booking API — main application entry point."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.config import settings
from app.database import engine, Base
from app.logging_config import setup_logging, get_logger
from app.middleware.rate_limit import limiter, wire_rate_limit
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
import asyncio
import traceback

# Import module routers
from app.modules.auth import router as auth_router
from app.modules.user import router as user_router
from app.modules.booking import router as booking_router
from app.modules.service import router as service_router
from app.modules.schedule import router as schedule_router
from app.modules.review import router as review_router
from app.modules.admin import router as admin_router
from app.modules.city import router as city_router
from app.modules.client import router as client_router
from app.modules.dadata.router import router as dadata_router
from app.modules.maxauth import router as max_router, webhook_router as max_webhook_router
from app.modules.vkauth import router as vk_router
from app.modules.yandexauth import router as yandex_router

# Инициализация логирования (LOG_LEVEL из env, иначе INFO в проде / DEBUG локально)
setup_logging(settings.log_level)
logger = get_logger(__name__)
logger.info("Инициализация приложения %s", settings.APP_NAME)


async def lifespan(app: FastAPI):
    """Application lifespan — create tables for SQLite, skip for PostgreSQL (Alembic)."""
    is_postgres = "postgres" in settings.DATABASE_URL
    if is_postgres:
        logger.info("База данных: PostgreSQL (Alembic migrations)")
    else:
        logger.info("База данных: SQLite (auto-create tables)")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    from app.services.auto_complete import auto_complete_loop
    auto_task = asyncio.create_task(auto_complete_loop())
    logger.info("Auto-complete loop started")
    from app.services.max_webhook_guard import max_webhook_guard_loop
    max_task = None
    if settings.max_enabled and settings.MAX_WEBHOOK_URL:
        max_task = asyncio.create_task(max_webhook_guard_loop())
        logger.info("MAX webhook guard loop started")
    elif settings.max_enabled:
        logger.info("MAX webhook guard off (MAX_WEBHOOK_URL not set)")
    yield
    auto_task.cancel()
    if max_task:
        max_task.cancel()


# ─── App creation ─────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "API для онлайн-записи в салон красоты.\n\n"
        "## Основные возможности\n"
        "- **Клиенты**: самостоятельная запись через веб-интерфейс, OTP-аутентификация по телефону\n"
        "- **Мастера**: управление услугами, расписанием, статистика\n"
        "- **Суперпользователь**: управление мастерами, клиентами, записями, аудиторские логи\n\n"
        "## Аутентификация\n"
        "Используйте Bearer-токен из `/api/v1/auth/login` или `/api/v1/auth/client/login` (OTP).\n\n"
        "## Версионирование\n"
        "Все API-эндпоинты версионированы: `/api/v1/`. "
        "Список изменений: `GET /api/v1/admin/changelog`."
    ),
    version="1.81.0",
    contact={
        "name": "Support",
        "email": "support@beauty-specialist.ru",
    },
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

# ─── Custom validation handlers (user-friendly error messages) ───

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return user-friendly validation errors (request body/query/path)."""
    details = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error.get("loc", []))
        msg = error.get("msg", "")
        details.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=422,
        content={"detail": details},
    )


@app.exception_handler(422)
async def http_422_handler(request: Request, exc: HTTPException):
    """Pass through manually raised HTTPException(422) untouched."""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.detail},
    )


# ─── Global 500 handler — log full traceback ───────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all for unhandled exceptions — log full traceback, return generic error."""
    request_id = getattr(request.state, "request_id", "-")
    logger.critical(
        "UNHANDLED EXCEPTION: %s %s | %s | %s: %s\n%s",
        request.method,
        request.url.path,
        request_id,
        type(exc).__name__,
        exc,
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
        exc_info=False,  # traceback already formatted above
    )
    # This handler runs in ServerErrorMiddleware (OUTSIDE every user
    # middleware, CORS included), so browsers would report the 500 as a
    # CORS failure and hide the body. Echo the origin back when allowed.
    headers = None
    origin = request.headers.get("origin")
    if origin and origin in settings.allowed_origins_list:
        headers = {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Vary": "Origin",
        }
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Внутренняя ошибка сервера",
            "request_id": request_id,
        },
        headers=headers,
    )

# ─── Middleware ────────────────────────────────────────────────
# ORDER MATTERS (Starlette: FIRST added = outermost):
# 1. Security headers first — every response carries them, including
#    429s and unhandled 500s.
# 2. CORS second — preflights are answered here and never reach the
#    limiter (no budget consumed); 429s flow back out through CORS.
# 3. SlowAPI third — budget enforced for real requests only.
# 4. Request logging last (innermost) — wraps the handler closely.
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    # Explicit list: "*" is invalid with allow_credentials=True per
    # the Fetch spec (browsers reject wildcard + credentials combo).
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Requested-With",
        "X-CSRF-Token",
    ],
)

wire_rate_limit(app)

# Request logging — INNERMOST user middleware so it wraps the handler closely
app.add_middleware(RequestLoggingMiddleware)

# ─── Health check ──────────────────────────────────────────────

@app.get("/health", tags=["system"])
@limiter.exempt
async def health_check():
    """System health check.
    
    Quick health check without database dependency.
    Use `/api/v1/admin/health` for full health check with DB and cache.
    
    **Example response:**
    ```json
    {
      "status": "ok",
      "app": "Online Booking API"
    }
    ```
    """
    return {"status": "ok", "app": settings.APP_NAME}

# ─── Import and include module routers ─────────────────────────

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(max_router, prefix="/api/v1/auth", tags=["max-auth"])
app.include_router(vk_router, prefix="/api/v1/auth", tags=["vk-auth"])
app.include_router(yandex_router, prefix="/api/v1/auth", tags=["yandex-auth"])
app.include_router(city_router, prefix="/api/v1", tags=["cities"])
app.include_router(user_router, prefix="/api/v1", tags=["users"])
app.include_router(booking_router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(service_router, prefix="/api/v1/services", tags=["services"])
app.include_router(schedule_router, prefix="/api/v1/working-hours", tags=["working-hours"])
app.include_router(review_router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(client_router, prefix="/api/v1/client", tags=["client"])
app.include_router(admin_router)  # admin endpoints (User model, modules/admin/)
app.include_router(dadata_router, prefix="/api/dadata")  # DAData address autocomplete proxy
app.include_router(max_webhook_router, prefix="/api/max", tags=["max-webhook"])

# Uploaded photos (avatars, certificates) — same-origin, no extra web server.
# Directory is created on first upload; missing dir is fine at startup.
import os as _os
from fastapi.staticfiles import StaticFiles as _StaticFiles
_static_dir = _os.path.join(_os.path.dirname(__file__), "static")
_os.makedirs(_static_dir, exist_ok=True)
app.mount("/static", _StaticFiles(directory=_static_dir), name="static")

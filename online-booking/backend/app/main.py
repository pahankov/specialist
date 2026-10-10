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
from app.modules.dadata.router import router as dadata_router
from app.modules.maxauth import router as max_router, webhook_router as max_webhook_router

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
    yield


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
    version="1.15.0",
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
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Внутренняя ошибка сервера",
            "request_id": request_id,
        },
    )

# ─── Middleware ────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# slowapi rate limiting (state + 429 handler + middleware; no-op in tests)
wire_rate_limit(app)

# Request logging — LAST middleware so it wraps everything
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
app.include_router(city_router, prefix="/api/v1", tags=["cities"])
app.include_router(user_router, prefix="/api/v1", tags=["users"])
app.include_router(booking_router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(service_router, prefix="/api/v1/services", tags=["services"])
app.include_router(schedule_router, prefix="/api/v1/working-hours", tags=["working-hours"])
app.include_router(review_router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(admin_router)  # admin endpoints (User model, modules/admin/)
app.include_router(dadata_router, prefix="/api/dadata")  # DAData address autocomplete proxy
app.include_router(max_webhook_router, prefix="/api/max", tags=["max-webhook"])

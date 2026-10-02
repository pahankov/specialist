"""Online Booking API — main application entry point."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.config import settings
from app.database import engine, Base
from app.logging_config import setup_logging, get_logger
from app.middleware.rate_limit import RateLimitMiddleware
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

# Инициализация логирования (DEBUG для разработки, INFO для продакшена)
setup_logging("DEBUG")
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
    version="1.5.0",
    contact={
        "name": "Support",
        "email": "support@beauty-specialist.ru",
    },
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

# ─── Custom 422 handler (better error messages) ────────────────

@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    """Return user-friendly validation errors."""
    # Only handle Pydantic ValidationErrors, not HTTPException(422)
    if not isinstance(exc, ValidationError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )
    details = []
    for error in exc.errors():
        loc = " -> ".join(str(l) for l in error.get("loc", []))
        msg = error.get("msg", "")
        details.append(f"{loc}: {msg}")
    return JSONResponse(
        status_code=422,
        content={"detail": details},
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
        "".join(traceback.format_exception(exc)),
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
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

# Request logging — LAST middleware so it wraps everything
app.add_middleware(RequestLoggingMiddleware)

# ─── Health check ──────────────────────────────────────────────

@app.get("/health", tags=["system"])
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
app.include_router(city_router, prefix="/api/v1", tags=["cities"])
app.include_router(user_router, prefix="/api/v1", tags=["users"])
app.include_router(booking_router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(service_router, prefix="/api/v1/services", tags=["services"])
app.include_router(schedule_router, prefix="/api/v1/working-hours", tags=["working-hours"])
app.include_router(review_router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(admin_router)  # admin endpoints (User model, modules/admin/)

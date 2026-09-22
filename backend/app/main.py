from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base
from app.logging_config import setup_logging, get_logger
from app.middleware import RateLimitMiddleware
import asyncio

# Инициализация логирования
setup_logging("INFO")
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


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Health endpoint
@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME}

# ─── Import and include module routers ────────────────────────────────
# Each module is a self-contained package with its own router.
# Adding a new feature: create modules/<feature>/ and include here.

from app.modules.auth import router as auth_router
from app.modules.user import router as user_router
from app.modules.booking import router as booking_router
from app.modules.service import router as service_router
from app.modules.schedule import router as schedule_router
from app.modules.review import router as review_router
from app.modules.admin import router as admin_router

app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(user_router, prefix="/api/v1", tags=["users"])
app.include_router(booking_router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(service_router, prefix="/api/v1/services", tags=["services"])
app.include_router(schedule_router, prefix="/api/v1/working-hours", tags=["working-hours"])
app.include_router(review_router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(admin_router)

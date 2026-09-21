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

# Import and include routers
from app.api import auth, masters, services, appointments, clients, working_hours, reviews, admin

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(masters.router, prefix="/api/v1/masters", tags=["masters"])
app.include_router(services.router, prefix="/api/v1/services", tags=["services"])
app.include_router(working_hours.router, prefix="/api/v1/working-hours", tags=["working-hours"])
app.include_router(appointments.router, prefix="/api/v1/appointments", tags=["appointments"])
app.include_router(clients.router, prefix="/api/v1/clients", tags=["clients"])
app.include_router(reviews.router, prefix="/api/v1/reviews", tags=["reviews"])
app.include_router(admin.router)

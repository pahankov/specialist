from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import logging
import os

logger = logging.getLogger(__name__)

db_url = settings.DATABASE_URL

# Handle SQLite path resolution
if "sqlite" in db_url:
    # Extract path from sqlite+aiosqlite:///path or sqlite:///path
    if "///" in db_url:
        db_path = db_url.split("///")[-1]
    elif "://" in db_url:
        db_path = db_url.split("://")[-1]
    else:
        db_path = db_url

    # Make path absolute if relative
    if not os.path.isabs(db_path):
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        db_path = os.path.join(backend_dir, db_path)

    # Ensure directory exists
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    db_url = f"sqlite+aiosqlite:///{db_path}"
    logger.info("SQLite database path: %s", db_path)

logger.info("Database URL: %s", db_url.replace("://", "://***@***" if "://" in db_url and "@" not in db_url.split("://")[1] else "://"))

engine = create_async_engine(
    db_url,
    echo=False,  # Disable SQL query logging — use SQLAlchemy logger instead
    # SQLite-specific: enable WAL mode for better concurrency
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
)

# Configure SQLAlchemy logger separately — only show slow queries or errors
sqlalchemy_logger = logging.getLogger("sqlalchemy")
sqlalchemy_logger.setLevel(logging.WARNING)  # Only warnings and errors
sqlalchemy_logger.propagate = True  # Let it go to root logger handlers

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    logger.debug("DB session created")
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            logger.warning("DB session rollback due to exception")
            await session.rollback()
            raise
        else:
            logger.debug("DB session committed successfully")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import os

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

engine = create_async_engine(
    db_url,
    echo=settings.DEBUG,
    # SQLite-specific: enable WAL mode for better concurrency
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {},
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

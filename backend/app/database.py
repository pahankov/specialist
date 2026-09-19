from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings
import os

db_url = settings.DATABASE_URL
if db_url.startswith("sqlite://"):
    # Convert to aiosqlite and ensure proper path
    db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    # Make path absolute if relative
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), db_path)
    # Ensure directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    db_url = f"sqlite+aiosqlite:///{db_path}"

engine = create_async_engine(db_url, echo=settings.DEBUG)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise

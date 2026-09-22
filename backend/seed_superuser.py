"""Seed script — create default superuser."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import select
from app.database import Base, AsyncSessionLocal
from app.models.master import Master
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_superuser():
    engine = create_async_engine("sqlite+aiosqlite:///./online_booking.db", echo=False)

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Master).where(Master.email == "pahankov@mail.ru"))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Master already exists: {existing.email}")
            return

        hashed = pwd_context.hash("SecurePass123!")
        master = Master(
            name="Павел",
            email="pahankov@mail.ru",
            hashed_password=hashed,
            phone="+7 (961) 520-23-11",
            is_admin=True,
        )
        session.add(master)
        await session.commit()
        print(f"[OK] Created superuser: {master.email} / SecurePass123!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_superuser())

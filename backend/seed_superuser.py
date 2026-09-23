"""Seed script — create default superuser."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.future import select
from app.database import Base, AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_superuser():
    engine = create_async_engine("sqlite+aiosqlite:///./online_booking.db", echo=False)

    # Create tables if they don't exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "pahankov@mail.ru"))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"Superuser already exists: {existing.email}")
            return

        hashed = pwd_context.hash("SecurePass123!")
        user = User(
            name="Павел",
            email="pahankov@mail.ru",
            hashed_password=hashed,
            phone="+7 (961) 520-23-11",
            role=UserRole.ADMIN,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.flush()

        # Create master profile
        master_profile = MasterProfile(
            user_id=user.id,
            telegram_username="pahankov",
        )
        session.add(master_profile)
        
        await session.commit()
        print(f"[OK] Created superuser: {user.email} / SecurePass123!")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_superuser())

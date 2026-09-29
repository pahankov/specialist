"""Create/update superuser using async SQLAlchemy.

Uses the same database connection as the main app — reads DATABASE_URL from .env.
Never overwrites existing superuser data (only updates role/password).

Usage:
    python create_superuser.py

Environment:
    DATABASE_URL - PostgreSQL connection string (reads from .env if not set)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.modules.auth.service import hash_password

SUPERUSER_EMAIL = "pahankov@mail.ru"
SUPERUSER_PASSWORD = "REDACTED_SUPERUSER_PASSWORD"
SUPERUSER_NAME = "Павел"
TELEGRAM_USERNAME = ""


async def main():
    print(f"Creating/updating superuser: {SUPERUSER_EMAIL}")

    async with AsyncSessionLocal() as session:
        # Find existing user
        result = await session.execute(
            select(User).where(User.email == SUPERUSER_EMAIL)
        )
        user = result.scalar_one_or_none()

        if user:
            print(f"  Found existing user (ID: {user.id})")
            user.hashed_password = hash_password(SUPERUSER_PASSWORD)
            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_verified = True
            print("  Superuser updated:")
        else:
            user = User(
                name=SUPERUSER_NAME,
                email=SUPERUSER_EMAIL,
                hashed_password=hash_password(SUPERUSER_PASSWORD),
                phone="+79615202311",
                role=UserRole.ADMIN,
                city_id=None,
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.flush()

            master_profile = MasterProfile(
                user_id=user.id,
                telegram_username=TELEGRAM_USERNAME,
                description="Суперпользователь",
                experience_years=10,
                is_available=True,
            )
            session.add(master_profile)
            print("  Superuser created:")

        await session.commit()

        print(f"    Email: {user.email}")
        print(f"    Password: {SUPERUSER_PASSWORD}")
        print(f"    ID: {user.id}")
        print(f"    Role: {user.role.value}")
        print(f"    Admin: {user.role == UserRole.ADMIN}")
        print(f"    Hashed: {user.hashed_password[:30]}...")
        print("\nGo to https://beauty-specialist.ru and login!")


if __name__ == "__main__":
    import asyncio
    from sqlalchemy import select
    asyncio.run(main())

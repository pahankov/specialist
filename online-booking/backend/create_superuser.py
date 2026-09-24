"""Create/update superuser script.

Usage:
    python create_superuser.py
"""
import asyncio
from sqlalchemy import select
from app.database import engine, AsyncSessionLocal, Base
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SUPERUSER_EMAIL = "pahankov@mail.ru"
SUPERUSER_PASSWORD = "Sug@r2026!"
SUPERUSER_NAME = "Павел"
TELEGRAM_USERNAME = "pahankov"


async def main():
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check if user already exists
        result = await session.execute(select(User).where(User.email == SUPERUSER_EMAIL))
        user = result.scalar_one_or_none()

        if user:
            # Update password and ensure admin role
            user.hashed_password = pwd_context.hash(SUPERUSER_PASSWORD)
            user.role = UserRole.ADMIN
            user.is_active = True
            print("Superuser updated:")
        else:
            # Create new superuser
            user = User(
                name=SUPERUSER_NAME,
                email=SUPERUSER_EMAIL,
                hashed_password=pwd_context.hash(SUPERUSER_PASSWORD),
                phone="+79615202311",
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.flush()

            # Create master profile for superuser
            master_profile = MasterProfile(
                user_id=user.id,
                telegram_username=TELEGRAM_USERNAME,
                description="Суперпользователь",
            )
            session.add(master_profile)
            print("Superuser created:")

        await session.commit()

        print(f"   Email: {user.email}")
        print(f"   Password: {SUPERUSER_PASSWORD}")
        print(f"   ID: {user.id}")
        print(f"   Role: {user.role.value}")
        print(f"   Admin: {user.is_admin}")
        print("\nGo to http://localhost:3000 and login!")


if __name__ == "__main__":
    asyncio.run(main())

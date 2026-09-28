"""Create/update superuser script.

Usage:
    python create_superuser.py
"""
import asyncio
import bcrypt
from sqlalchemy import select
from app.database import engine, AsyncSessionLocal, Base
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile

SUPERUSER_EMAIL = "pahankov@mail.ru"
SUPERUSER_PASSWORD = "REDACTED_SUPERUSER_PASSWORD"
SUPERUSER_NAME = "Павел"
TELEGRAM_USERNAME = "pahankov"


def _hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


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
            user.hashed_password = _hash_pw(SUPERUSER_PASSWORD)
            user.role = UserRole.ADMIN
            user.is_active = True
            print("Superuser updated:")
        else:
            # Create new superuser
            user = User(
                name=SUPERUSER_NAME,
                email=SUPERUSER_EMAIL,
                hashed_password=_hash_pw(SUPERUSER_PASSWORD),
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

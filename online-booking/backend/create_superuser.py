"""Create/update superuser using async SQLAlchemy.

Uses the same database connection as the main app — reads DATABASE_URL from .env.
Credentials come ONLY from the environment (server .env / GitHub Secrets),
never hardcoded — a hardcoded value would be rewritten by history scrubbing
and silently reset the production password on every deploy.

Behavior:
- Existing user: ensures ADMIN role + active/verified. Password is updated
  ONLY when SUPERUSER_PASSWORD is set; otherwise the stored hash is kept.
- Missing user: requires both SUPERUSER_EMAIL and SUPERUSER_PASSWORD,
  otherwise exits non-zero (fail fast instead of creating a broken account).

Usage:
    SUPERUSER_EMAIL=admin@example.com SUPERUSER_PASSWORD=<secret> \\
        python create_superuser.py

Environment:
    DATABASE_URL - PostgreSQL connection string (reads from .env if not set)
    SUPERUSER_EMAIL - admin login (required to create, optional to update)
    SUPERUSER_PASSWORD - admin password (required to create or rotate)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.utils.security import hash_password

SUPERUSER_NAME = "Павел"
TELEGRAM_USERNAME = ""


def _masked() -> str:
    return "<set>" if os.getenv("SUPERUSER_PASSWORD") else "<empty>"


async def ensure_superuser(session, email: str, password: str | None) -> User:
    """Create or update the superuser in the given session. Returns the user.

    password=None keeps the existing hash (used by routine deploys).
    """
    from sqlalchemy import select

    result = await session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        print(f"  Found existing user (ID: {user.id})")
        if password:
            user.hashed_password = hash_password(password)
            print("  Password rotated from env")
        else:
            print("  Password kept (SUPERUSER_PASSWORD not set)")
        user.role = UserRole.ADMIN
        user.is_active = True
        user.is_verified = True
        print("  Superuser updated:")
    else:
        if not password:
            print(
                "ERROR: superuser does not exist and SUPERUSER_PASSWORD is not set. "
                "Refusing to create a password-less admin.",
                file=sys.stderr,
            )
            raise SystemExit(1)
        user = User(
            name=SUPERUSER_NAME,
            email=email,
            hashed_password=hash_password(password),
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
            status="active",
            is_active=True,
        )
        session.add(master_profile)
        print("  Superuser created:")

    await session.commit()

    print(f"    Email: {user.email}")
    print(f"    Password: {_masked()}")
    print(f"    ID: {user.id}")
    print(f"    Role: {user.role.value}")
    print(f"    Admin: {user.role == UserRole.ADMIN}")
    print("\nGo to https://beauty-specialist.ru and login!")
    return user


async def main():
    email = os.getenv("SUPERUSER_EMAIL", "")
    password = os.getenv("SUPERUSER_PASSWORD") or None
    if not email:
        print(
            "ERROR: SUPERUSER_EMAIL is not set (server .env / GitHub Secrets).",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"Creating/updating superuser: {email} (password {_masked()})")

    async with AsyncSessionLocal() as session:
        await ensure_superuser(session, email, password)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

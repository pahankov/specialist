"""Create/update superuser using sync SQLAlchemy.

Usage:
    python create_superuser_sync.py

Uses synchronous SQLAlchemy (create_engine + psycopg2) to avoid
timezone-aware datetime errors on PostgreSQL.
"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.database import Base
from passlib.context import CryptContext

# Database URL from environment or default
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/online_booking"
)

SUPERUSER_EMAIL = "pahankov@mail.ru"
SUPERUSER_PASSWORD = "REDACTED_SUPERUSER_PASSWORD"
SUPERUSER_NAME = "Павел"
TELEGRAM_USERNAME = "pahankov"


def main():
    print(f"Connecting to: {DATABASE_URL}")

    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.email == SUPERUSER_EMAIL)
        ).scalar_one_or_none()

        if user:
            user.hashed_password = pwd_context.hash(SUPERUSER_PASSWORD)
            user.role = UserRole.ADMIN
            user.is_active = True
            print("Superuser updated:")
        else:
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
            session.flush()

            master_profile = MasterProfile(
                user_id=user.id,
                telegram_username=TELEGRAM_USERNAME,
                description="Суперпользователь",
            )
            session.add(master_profile)
            print("Superuser created:")

        session.commit()

        print(f"   Email: {user.email}")
        print(f"   Password: {SUPERUSER_PASSWORD}")
        print(f"   ID: {user.id}")
        print(f"   Role: {user.role.value}")
        print(f"   Admin: {user.is_admin}")
        print("\nGo to https://beauty-specialist.ru and login!")


if __name__ == "__main__":
    main()

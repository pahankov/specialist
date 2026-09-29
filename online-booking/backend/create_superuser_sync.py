"""Create/update superuser using sync SQLAlchemy.

This script is fully self-contained — it does NOT import from app.database
(because app.database always creates an async engine, which fails when
DATABASE_URL uses psycopg2).

Uses bcrypt directly (not passlib) to avoid passlib/bcrypt >= 4.0 incompatibility.

Usage:
    python create_superuser_sync.py

Environment:
    DATABASE_URL - PostgreSQL connection string (reads from .env if not set)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

# Try to load .env file for local development
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
except ImportError:
    pass

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime,
    Enum as SAEnum, ForeignKey, create_engine, select,
)
from sqlalchemy.orm import sessionmaker, declarative_base
import bcrypt
import enum
import datetime

Base = declarative_base()


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MASTER = "master"
    CLIENT = "client"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(SAEnum(UserRole), default=UserRole.CLIENT, nullable=False)
    city_id = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class MasterProfile(Base):
    __tablename__ = "master_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    telegram_username = Column(String, nullable=True)
    description = Column(String, nullable=True)
    experience_years = Column(Integer, nullable=True)
    is_available = Column(Boolean, default=True)


# Read DATABASE_URL from environment (set by deploy.yml) or use hardcoded production URL
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://specialist:REDACTED_DB_PASSWORD@localhost:5432/online_booking"
)

SUPERUSER_EMAIL = "pahankov@mail.ru"
SUPERUSER_PASSWORD = "REDACTED_SUPERUSER_PASSWORD"
SUPERUSER_NAME = "Павел"
TELEGRAM_USERNAME = ""


def hash_password(plain: str) -> str:
    """Hash password using bcrypt directly."""
    return bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def main():
    print(f"Connecting to: {DATABASE_URL}")

    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine)

    with SessionLocal() as session:
        user = session.execute(
            select(User).where(User.email == SUPERUSER_EMAIL)
        ).scalar_one_or_none()

        if user:
            user.hashed_password = hash_password(SUPERUSER_PASSWORD)
            user.role = UserRole.ADMIN
            user.is_active = True
            user.is_verified = True
            print("Superuser updated:")
        else:
            user = User(
                name=SUPERUSER_NAME,
                email=SUPERUSER_EMAIL,
                hashed_password=hash_password(SUPERUSER_PASSWORD),
                phone="+79615202311",
                role=UserRole.ADMIN,
                city_id=None,  # Superuser doesn't need city_id
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            session.flush()

            master_profile = MasterProfile(
                user_id=user.id,
                telegram_username=TELEGRAM_USERNAME,
                description="Суперпользователь",
                experience_years=10,
                is_available=True,
            )
            session.add(master_profile)
            print("Superuser created:")

        session.commit()

        print(f"   Email: {user.email}")
        print(f"   Password: {SUPERUSER_PASSWORD}")
        print(f"   ID: {user.id}")
        print(f"   Role: {user.role.value}")
        print(f"   Admin: {user.role == UserRole.ADMIN}")
        print(f"   Hashed: {user.hashed_password[:30]}...")
        print("\nGo to https://beauty-specialist.ru and login!")


if __name__ == "__main__":
    main()

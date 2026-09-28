"""Create/update superuser using sync SQLAlchemy.

This script is fully self-contained — it does NOT import from app.database
(because app.database always creates an async engine, which fails when
DATABASE_URL uses psycopg2).

Usage:
    python create_superuser_sync.py

Uses synchronous SQLAlchemy (create_engine + psycopg2) to avoid
timezone-aware datetime errors on PostgreSQL.
"""
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Table,
    MetaData,
    create_engine,
    select,
)
from sqlalchemy.orm import sessionmaker, relationship
from passlib.context import CryptContext
import enum
import datetime

# ---------------------------------------------------------------------------
# Minimal model definitions (mirrors app.models without importing them)
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    MASTER = "master"
    CLIENT = "client"


class UserBase:
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    email = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class MasterProfileBase:
    __tablename__ = "master_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    telegram_username = Column(String, nullable=True)
    description = Column(String, nullable=True)
    experience_years = Column(Integer, nullable=True)
    is_available = Column(Boolean, default=True)


# ---------------------------------------------------------------------------
# Database setup
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:postgres@localhost:5432/online_booking"
)

SUPERUSER_EMAIL = "pahankov@mail.ru"
SUPERUSER_PASSWORD = "Sug@r2026!"
SUPERUSER_NAME = "Павел"
TELEGRAM_USERNAME = "pahankov"


def main():
    print(f"Connecting to: {DATABASE_URL}")

    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(engine)
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    with SessionLocal() as session:
        # Check if user exists
        user_stmt = select(UserBase).where(UserBase.email == SUPERUSER_EMAIL)
        user = session.execute(user_stmt).scalar_one_or_none()

        if user:
            user.hashed_password = pwd_context.hash(SUPERUSER_PASSWORD)
            user.role = UserRole.ADMIN
            user.is_active = True
            print("Superuser updated:")
        else:
            user = UserBase(
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

            master_profile = MasterProfileBase(
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
        print(f"   Admin: {user.role == UserRole.ADMIN}")
        print("\nGo to https://beauty-specialist.ru and login!")


if __name__ == "__main__":
    main()

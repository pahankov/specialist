"""Create/update superuser using sync SQLAlchemy.

This script is fully self-contained — it does NOT import from app.database
(because app.database always creates an async engine, which fails when
DATABASE_URL uses psycopg2).

Uses bcrypt directly (not passlib) to avoid passlib/bcrypt >= 4.0 incompatibility.

Usage:
    python create_superuser_sync.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

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


DATABASE_URL = "postgresql+psycopg2://specialist:Postgres2024!Secure@localhost:5432/online_booking"

SUPERUSER_EMAIL = "pahankov@mail.ru"
SUPERUSER_PASSWORD = "Sug@r2026!"
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
            print("Superuser updated:")
        else:
            user = User(
                name=SUPERUSER_NAME,
                email=SUPERUSER_EMAIL,
                hashed_password=hash_password(SUPERUSER_PASSWORD),
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
        print(f"   Admin: {user.role == UserRole.ADMIN}")
        print(f"   Hashed: {user.hashed_password[:30]}...")
        print("\nGo to https://beauty-specialist.ru and login!")


if __name__ == "__main__":
    main()

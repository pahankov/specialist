"""Fix production database issues.

This script:
1. Creates countries and cities if they don't exist
2. Verifies superuser exists and has ADMIN role
3. Creates MasterProfile for superuser if missing

Usage:
    python fix_production_db.py

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

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SAEnum, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker
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
    is_active = Column(Boolean, default=True)


class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True)
    code = Column(String(3), nullable=False, unique=True)
    name_ru = Column(String(100), nullable=False)
    name_en = Column(String(100), nullable=False)
    phone_prefix = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True)


class City(Base):
    __tablename__ = "cities"

    id = Column(Integer, primary_key=True)
    country_id = Column(Integer, ForeignKey("countries.id", ondelete="CASCADE"), nullable=False)
    name_ru = Column(String(200), nullable=False)
    name_en = Column(String(200), nullable=True)
    slug = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)


def hash_password(plain: str) -> str:
    """Hash password using bcrypt directly."""
    return bcrypt.hashpw(
        plain.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def fix_geography(session):
    """Create countries and cities if they don't exist."""
    print("\n🌍 Checking geography data...")
    
    result = session.execute(select(Country).limit(1))
    if result.scalar_one_or_none():
        print("  ✓ Geography data already exists")
        return
    
    print("  Creating countries and cities...")
    
    # Create countries
    countries_data = [
        Country(
            code="RU",
            name_ru="Россия",
            name_en="Russia",
            phone_prefix="+7",
            is_active=True,
        ),
        Country(
            code="KZ",
            name_ru="Казахстан",
            name_en="Kazakhstan",
            phone_prefix="+7",
            is_active=True,
        ),
        Country(
            code="BY",
            name_ru="Беларусь",
            name_en="Belarus",
            phone_prefix="+375",
            is_active=True,
        ),
    ]
    
    for country in countries_data:
        session.add(country)
    
    session.commit()
    
    # Get Russia
    russia = session.execute(select(Country).where(Country.code == "RU")).scalar_one()
    
    # Create cities
    russian_cities = [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
        "Казань", "Нижний Новгород", "Челябинск", "Самара",
        "Омск", "Ростов-на-Дону", "Уфа", "Красноярск",
        "Воронеж", "Пермь", "Волгоград",
    ]
    
    for city_name in russian_cities:
        city = City(
            country_id=russia.id,
            name_ru=city_name,
            name_en=city_name,
            slug=city_name.lower().replace(" ", "-"),
            is_active=True,
        )
        session.add(city)
    
    session.commit()
    print(f"  ✓ Created {len(countries_data)} countries and {len(russian_cities)} cities")


def fix_superuser(session, email, password):
    """Verify superuser exists with ADMIN role and has MasterProfile."""
    print("\n👑 Checking superuser...")
    
    result = session.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        print(f"  Creating superuser: {email}")
        user = User(
            name="Павел",
            email=email,
            hashed_password=hash_password(password),
            phone="+79615202311",
            role=UserRole.ADMIN,
            city_id=None,
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        session.flush()
        
        master_profile = MasterProfile(
            user_id=user.id,
            telegram_username="",
            description="Суперпользователь",
            experience_years=10,
            is_available=True,
        )
        session.add(master_profile)
        session.commit()
        print(f"  ✓ Superuser created (ID: {user.id})")
    else:
        print(f"  Found user: {user.email} (ID: {user.id})")
        
        # Fix role
        if user.role != UserRole.ADMIN:
            print(f"  Changing role from {user.role.value} to ADMIN")
            user.role = UserRole.ADMIN
        else:
            print(f"  ✓ Role is already ADMIN")
        
        # Fix active status
        if not user.is_active:
            print(f"  Activating user")
            user.is_active = True
        else:
            print(f"  ✓ User is active")
        
        # Fix password
        print(f"  Updating password")
        user.hashed_password = hash_password(password)
        
        session.commit()
        
        # Check MasterProfile
        result = session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )
        master_profile = result.scalar_one_or_none()
        
        if not master_profile:
            print(f"  Creating MasterProfile for superuser")
            master_profile = MasterProfile(
                user_id=user.id,
                telegram_username="",
                description="Суперпользователь",
                experience_years=10,
                is_available=True,
            )
            session.add(master_profile)
            session.commit()
            print(f"  ✓ MasterProfile created")
        else:
            print(f"  ✓ MasterProfile exists")
    
    return user


def main():
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg2://specialist:Postgres2024!Secure@localhost:5432/online_booking"
    )
    
    SUPERUSER_EMAIL = "pahankov@mail.ru"
    SUPERUSER_PASSWORD = "Sug@r2026!"
    
    print(f"Connecting to: {DATABASE_URL}")
    
    engine = create_engine(DATABASE_URL)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(engine)
    
    with SessionLocal() as session:
        # Fix geography
        fix_geography(session)
        
        # Fix superuser
        user = fix_superuser(session, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        
        print("\n" + "="*60)
        print("✅ All fixes applied successfully!")
        print("="*60)
        print(f"\nSuperuser credentials:")
        print(f"  Email: {SUPERUSER_EMAIL}")
        print(f"  Password: {SUPERUSER_PASSWORD}")
        print(f"  Role: {user.role.value}")
        print(f"  Admin: {user.role == UserRole.ADMIN}")
        print(f"\nGo to https://beauty-specialist.ru and login!")


if __name__ == "__main__":
    main()

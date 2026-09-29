"""Fix production database issues using async SQLAlchemy.

This script:
1. Creates countries and cities if they don't exist
2. Verifies superuser exists and has ADMIN role
3. Creates MasterProfile for superuser if missing

Uses the same database connection as the main app.

Usage:
    python fix_production_db.py

Environment:
    DATABASE_URL - PostgreSQL connection string (reads from .env if not set)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.country import Country
from app.models.city import City
from app.modules.auth.service import hash_password


async def fix_geography(session):
    """Create countries and cities if they don't exist."""
    print("\n🌍 Checking geography data...")
    
    result = await session.execute(select(Country).limit(1))
    if result.scalar_one_or_none():
        print("  ✓ Geography data already exists")
        return
    
    print("  Creating countries and cities...")
    
    countries_data = [
        Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7", is_active=True),
        Country(code="KZ", name_ru="Казахстан", name_en="Kazakhstan", phone_prefix="+7", is_active=True),
        Country(code="BY", name_ru="Беларусь", name_en="Belarus", phone_prefix="+375", is_active=True),
    ]
    
    for country in countries_data:
        session.add(country)
    
    await session.commit()
    
    russia = await session.execute(select(Country).where(Country.code == "RU"))
    russia = russia.scalar_one()
    
    russian_cities = [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
        "Казань", "Нижний Новгород", "Челябинск", "Самара",
        "Омск", "Ростов-на-Дону", "Уфа", "Красноярск",
        "Воронеж", "Пермь", "Волгоград",
    ]
    
    for city_name in russian_cities:
        session.add(City(
            country_id=russia.id,
            name_ru=city_name,
            name_en=city_name,
            slug=city_name.lower().replace(" ", "-"),
            is_active=True,
        ))
    
    await session.commit()
    print(f"  ✓ Created {len(countries_data)} countries and {len(russian_cities)} cities")


async def fix_superuser(session, email, password):
    """Verify superuser exists with ADMIN role and has MasterProfile."""
    print("\n👑 Checking superuser...")
    
    result = await session.execute(select(User).where(User.email == email))
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
        await session.flush()
        
        master_profile = MasterProfile(
            user_id=user.id,
            telegram_username="",
            description="Суперпользователь",
            experience_years=10,
            is_available=True,
        )
        session.add(master_profile)
        await session.commit()
        print(f"  ✓ Superuser created (ID: {user.id})")
    else:
        print(f"  Found user: {user.email} (ID: {user.id})")
        
        if user.role != UserRole.ADMIN:
            print(f"  Changing role from {user.role.value} to ADMIN")
            user.role = UserRole.ADMIN
        else:
            print(f"  ✓ Role is already ADMIN")
        
        if not user.is_active:
            print(f"  Activating user")
            user.is_active = True
        else:
            print(f"  ✓ User is active")
        
        print(f"  Updating password")
        user.hashed_password = hash_password(password)
        
        await session.commit()
        
        result = await session.execute(
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
            await session.commit()
            print(f"  ✓ MasterProfile created")
        else:
            print(f"  ✓ MasterProfile exists")
    
    return user


async def main():
    DATABASE_URL = os.environ.get("DATABASE_URL", "Not set")
    SUPERUSER_EMAIL = "pahankov@mail.ru"
    SUPERUSER_PASSWORD = "Sug@r2026!"
    
    print(f"Connecting to: {DATABASE_URL}")
    
    async with AsyncSessionLocal() as session:
        await fix_geography(session)
        user = await fix_superuser(session, SUPERUSER_EMAIL, SUPERUSER_PASSWORD)
        
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
    import asyncio
    from sqlalchemy import select
    asyncio.run(main())

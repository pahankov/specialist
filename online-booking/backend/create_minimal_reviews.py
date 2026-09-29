"""Create minimal test data for reviews to work on fresh deployments.

This script creates:
- 3 sample masters (if none exist)
- 5 completed appointments (if none exist)  
- Reviews for those appointments (if none exist)

Safe to run on any server — never overwrites existing data.

Usage:
    python create_minimal_reviews.py
"""
import asyncio
import sys
import os
import random
from datetime import datetime, timedelta, timezone, date, time

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select, text
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile, MasterStatus
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.review import Review
from app.models.country import Country
from app.models.city import City
import bcrypt


def _hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


async def ensure_geography(db):
    """Create countries and cities if missing."""
    result = await db.execute(select(Country).limit(1))
    if result.scalar_one_or_none():
        return
    
    countries_data = [
        Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7", is_active=True),
        Country(code="KZ", name_ru="Казахстан", name_en="Kazakhstan", phone_prefix="+7", is_active=True),
        Country(code="BY", name_ru="Беларусь", name_en="Belarus", phone_prefix="+375", is_active=True),
    ]
    for c in countries_data:
        db.add(c)
    await db.commit()
    
    russia = await db.execute(select(Country).where(Country.code == "RU"))
    russia = russia.scalar_one()
    
    cities = [
        "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург",
        "Казань", "Нижний Новгород", "Челябинск", "Самара",
        "Омск", "Ростов-на-Дону", "Уфа", "Красноярск",
        "Воронеж", "Пермь", "Волгоград",
    ]
    for name in cities:
        db.add(City(country_id=russia.id, name_ru=name, name_en=name, slug=name.lower().replace(" ", "-"), is_active=True))
    await db.commit()
    print("  ✓ Geography ready")


async def ensure_masters(db):
    """Create 3 sample masters if none exist."""
    result = await db.execute(select(User).where(User.role == UserRole.MASTER).limit(1))
    if result.scalar_one_or_none():
        return
    
    now = datetime.now(timezone.utc)
    masters_data = [
        ("Анна Смирнова", "anna@beauty.ru", "+79001000001", "Мастер маникюра с опытом 8 лет"),
        ("Елена Козлова", "elena@beauty.ru", "+79001000002", "Стилист-колорист премиум класса"),
        ("Мария Петрова", "maria@beauty.ru", "+79001000003", "Мастер бровей и ресниц"),
    ]
    
    for name, email, phone, desc in masters_data:
        user = User(
            name=name, email=email, phone=phone,
            hashed_password=_hash_pw("password123"),
            role=UserRole.MASTER, is_active=True, is_verified=True,
            created_at=now - timedelta(days=random.randint(30, 365)),
        )
        db.add(user)
        await db.flush()
        
        db.add(MasterProfile(
            user_id=user.id, description=desc, telegram_username=f"@{name.split()[0].lower()}",
            experience_years=random.randint(3, 12), status=MasterStatus.ACTIVE, is_active=True,
            created_at=user.created_at,
        ))
    
    await db.commit()
    print("  ✓ 3 sample masters created")


async def ensure_services(db):
    """Create services for each master if none exist."""
    result = await db.execute(select(Service).limit(1))
    if result.scalar_one_or_none():
        return
    
    now = datetime.now(timezone.utc)
    
    # Get all masters
    result = await db.execute(select(User).where(User.role == UserRole.MASTER))
    masters = result.scalars().all()
    
    service_templates = [
        ("Маникюр классический", 60, 1500),
        ("Маникюр гель-лак", 90, 2500),
        ("Педикюр полный", 120, 3500),
        ("Окрашивание волос", 120, 5000),
        ("Стрижка женская", 60, 2000),
        ("Брови архитектура", 60, 2000),
    ]
    
    for master in masters:
        mp_result = await db.execute(select(MasterProfile).where(MasterProfile.user_id == master.id))
        mp = mp_result.scalar_one_or_none()
        if not mp:
            continue
        
        chosen = random.sample(service_templates, min(4, len(service_templates)))
        for svc_name, duration, price in chosen:
            db.add(Service(
                master_id=mp.id, name=svc_name,
                description=f"Услуга от мастера {master.name}",
                duration_minutes=duration, price=price, is_active=True,
                created_at=now - timedelta(days=random.randint(10, 300)),
            ))
    
    await db.commit()
    print("  ✓ Services created for all masters")


async def ensure_appointments(db):
    """Create completed appointments if none exist (needed for reviews)."""
    result = await db.execute(select(text('count(*)')).select_from(text('appointments')))
    count = result.scalar() or 0
    if count > 0:
        return
    
    now = datetime.now(timezone.utc)
    
    # Get masters
    result = await db.execute(select(MasterProfile))
    masters = result.scalars().all()
    
    if not masters:
        print("  ⚠ No masters found, skipping appointments")
        return
    
    # Create a few clients
    clients = []
    for i in range(5):
        user = User(
            name=f"Клиент {i+1}", email=f"client{i}@test.ru",
            phone=f"+7911{2000000 + i:06d}",
            hashed_password=None, role=UserRole.CLIENT,
            is_active=True, is_verified=True,
            created_at=now - timedelta(days=random.randint(5, 100)),
        )
        db.add(user)
        await db.flush()
        clients.append(user)
    await db.commit()
    
    # Get services
    result = await db.execute(select(Service).where(Service.is_active == True))
    services = result.scalars().all()
    
    if not services:
        print("  ⚠ No services found, skipping appointments")
        return
    
    # Create 10 completed appointments
    for i in range(10):
        master = random.choice(masters)
        client = random.choice(clients)
        service = random.choice(services)
        
        days_ago = random.randint(10, 90)
        appt_date = now - timedelta(days=days_ago, hours=random.randint(8, 18))
        
        appt = Appointment(
            master_id=master.id,
            service_id=service.id,
            client_id=client.id,
            appointment_date=appt_date,
            status="completed",
            notes=random.choice(["Постоянный клиент", "Через сайт", "По рекомендации", None]),
            created_at=appt_date - timedelta(days=random.randint(1, 5)),
        )
        db.add(appt)
    
    await db.commit()
    print("  ✓ 10 completed appointments created")


async def ensure_reviews(db):
    """Create reviews for completed appointments if none exist."""
    result = await db.execute(select(text('count(*)')).select_from(text('reviews')))
    count = result.scalar() or 0
    if count > 0:
        print(f"  ✓ Reviews already exist ({count} records)")
        return
    
    # Get completed appointments
    result = await db.execute(select(Appointment).where(Appointment.status == "completed"))
    completed = result.scalars().all()
    
    if not completed:
        print("  ⚠ No completed appointments, skipping reviews")
        return
    
    now = datetime.now(timezone.utc)
    comments = [
        "Отличный мастер! Рекомендую!",
        "Очень довольна результатом",
        "Буду приходить ещё",
        "Профессиональный подход",
        "Всё понравилось, спасибо!",
        "Хороший сервис, приятная атмосфера",
        "Мастер — золото!",
        "Быстро и качественно",
    ]
    
    review_count = 0
    for appt in completed:
        if random.random() > 0.3:  # 70% have reviews
            cp_result = await db.execute(
                select(User).where(User.id == appt.client_profile.user_id)
            )
            user = cp_result.scalar_one_or_none()
            client_name = user.name if user else "Аноним"
            client_phone = user.phone if user else "+7***"
            
            rating = random.choices([4, 5], weights=[0.3, 0.7], k=1)[0]
            
            review = Review(
                appointment_id=appt.id,
                master_id=appt.master_id,
                client_name=client_name,
                client_phone=client_phone,
                rating=rating,
                comment=random.choice(comments),
                is_published=True,
                created_at=appt.appointment_date + timedelta(days=random.randint(1, 7)),
            )
            db.add(review)
            review_count += 1
    
    await db.commit()
    print(f"  ✓ {review_count} reviews created")


async def main():
    print("🔧 Creating minimal data for reviews to work...\n")
    
    async with AsyncSessionLocal() as db:
        await ensure_geography(db)
        await ensure_masters(db)
        await ensure_services(db)
        await ensure_appointments(db)
        await ensure_reviews(db)
    
    print("\n✅ Minimal data created successfully!")
    print("   Masters login: master0@beauty.ru / password123")
    print("   (sample masters created on this run)")


if __name__ == "__main__":
    asyncio.run(main())

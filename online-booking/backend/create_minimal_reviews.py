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
from app.utils.security import hash_password
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile, MasterStatus
from app.models.service import Service
from app.models.appointment import Appointment
from app.models.review import Review




async def ensure_geography(db):
    """Canonical geography top-up (delegates to seed_common)."""
    from seed_common import ensure_geography as _ensure_geo
    await _ensure_geo(db)
    print("  Geography ready")




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
            hashed_password=hash_password("password123"),
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
    """Canonical review seeding (delegates to seed_common.ensure_reviews)."""
    from seed_common import ensure_reviews as _ensure_reviews
    await _ensure_reviews(db)




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

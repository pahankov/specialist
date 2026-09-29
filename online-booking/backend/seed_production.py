"""Seed production data — always run geography, conditionally run full seed.

Usage:
    python seed_production.py          # Always creates geography + reviews
    python seed_production.py --full   # Creates full test data (masters, clients, etc.)

Behavior:
    - Geography (countries/cities) is ALWAYS created if missing
    - Reviews are ALWAYS created if missing (from existing appointments)
    - Full test data (masters, clients, appointments) is created only with --full flag
    - Or if users table is completely empty
"""
import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select, text
from app.database import AsyncSessionLocal


async def seed_geography_only():
    """Create countries and cities if missing — always safe to run."""
    print("\n🌍 Seeding geography (countries/cities)...")
    from seed_test_data import seed_geography
    async with AsyncSessionLocal() as session:
        await seed_geography(session)


async def seed_reviews_only():
    """Create reviews from existing appointments — safe to run anytime."""
    print("\n⭐ Seeding reviews from existing appointments...")
    from app.models.user import User, UserRole
    from app.models.appointment import Appointment
    from app.models.review import Review
    import random
    from datetime import datetime, timezone
    
    random.seed(42)
    now = datetime.now(timezone.utc)
    
    async with AsyncSessionLocal() as session:
        # Check if reviews already exist
        result = await session.execute(select(text('count(*)')).select_from(text('reviews')))
        count = result.scalar()
        if count and count > 0:
            print(f"  Reviews already exist ({count} records). Skipping.")
            return
        
        # Get completed appointments
        result = await session.execute(
            select(Appointment).where(Appointment.status == "completed")
        )
        completed_appts = result.scalars().all()
        
        if not completed_appts:
            print("  No completed appointments found. Skipping reviews.")
            return
        
        review_count = 0
        for appt in completed_appts:
            if random.random() > 0.4:  # 60% of completed have reviews
                # Get client name
                cp_result = await session.execute(
                    select(User).where(User.id == appt.client_profile.user_id)
                )
                user = cp_result.scalar_one_or_none()
                client_name = user.name if user else "Аноним"
                client_phone = user.phone if user else "+7***"
                
                rating = random.choices([3, 4, 5], weights=[0.1, 0.3, 0.6], k=1)[0]
                comments = [
                    "Отличный мастер! Рекомендую!",
                    "Очень довольна результатом",
                    "Буду приходить ещё",
                    "Профессиональный подход",
                    "Всё понравилось, спасибо!",
                    "Хороший сервис",
                    "Мастер — золото!",
                ]
                
                review = Review(
                    appointment_id=appt.id,
                    master_id=appt.master_id,
                    client_name=client_name,
                    client_phone=client_phone,
                    rating=rating,
                    comment=random.choice(comments),
                    is_published=True,
                    created_at=appt.appointment_date + __import__('datetime').timedelta(days=random.randint(1, 7)),
                )
                session.add(review)
                review_count += 1
        
        await session.commit()
        print(f"  [OK] Created {review_count} reviews")


async def seed_full():
    """Full seed: masters, clients, appointments, reviews, working hours."""
    from seed_test_data import create_seed_data
    await create_seed_data()
    print("\nFull seed completed successfully.")


async def main():
    force_full = "--full" in sys.argv
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(text('count(*)')).select_from(text('users')))
        count = result.scalar() or 0
    
    if force_full:
        print("⚡ Full seed mode (with --full flag)")
        await seed_geography_only()
        await seed_full()
    elif count == 0:
        print("📦 Users table is empty. Running full seed...")
        await seed_geography_only()
        await seed_full()
    else:
        print(f"📦 Users table has {count} record(s).")
        print("Running safe seed (geography + reviews only)...")
        await seed_geography_only()
        await seed_reviews_only()
        print("\nℹ️  To create full test data (masters, clients, appointments), run:")
        print("   python seed_production.py --full")


if __name__ == "__main__":
    asyncio.run(main())

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
    """Create countries and cities if missing - always safe to run."""
    print("  Seeding geography (countries/cities)...")
    from seed_common import ensure_geography
    async with AsyncSessionLocal() as session:
        await ensure_geography(session)


async def seed_reviews_only():
    """Create reviews from existing appointments - safe to run anytime."""
    print("  Seeding reviews from existing appointments...")
    from seed_common import ensure_reviews
    async with AsyncSessionLocal() as session:
        await ensure_reviews(session)




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

"""Seed production data if DB is empty.

Usage:
    python seed_production.py

Creates seed data only if the users table is empty.
Never overwrites existing production data.
"""
import asyncio
import sys
import os

# Add backend directory to path
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select, text
from app.database import AsyncSessionLocal


async def seed_if_empty():
    """Seed production data only if DB is completely empty."""
    async with AsyncSessionLocal() as session:
        # Check if any users exist
        result = await session.execute(select(text('count(*)')).select_from(text('users')))
        count = result.scalar()

        if count > 0:
            print(f"Users table has {count} record(s). Skipping seed — production data preserved.")
            return

        print("Users table is empty. Running seed data creation...")

    # Import and run the full seed script (it handles protected users)
    from seed_test_data import create_seed_data
    await create_seed_data()
    print("\nProduction seed completed successfully.")


if __name__ == "__main__":
    asyncio.run(seed_if_empty())

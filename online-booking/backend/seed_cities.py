"""Seed script for countries and cities.

Usage:
    python seed_cities.py

Requires: database must be migrated first (alembic upgrade head).
"""
import asyncio
import sys
import os

# Add backend dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.country import Country
from app.models.city import City
from app.database import Base, engine


# ─── Data ─────────────────────────────────────────────────────────────

from seed_common import COUNTRIES, ensure_geography

async def seed():
    async with engine.begin() as conn:
        # Only create tables if they don't exist (skip if Alembic not run)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSession(engine) as session:
        new_c, new_t = await ensure_geography(session)

    print(f"  Seeded {len(COUNTRIES)} countries ({new_c} new) and {new_t} new cities (idempotent top-up)")

if __name__ == "__main__":
    import asyncio
    from sqlalchemy import select

    print("Seeding countries and cities...")
    asyncio.run(seed())
    print("Done!")

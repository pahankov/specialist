"""Fix: Add working hours to masters with 0 active days.

During deployment, this ensures all masters have at least some working days
so they appear as active in the public API (/api/v1/masters/).

Usage:
    python fix_production_masters.py

Environment:
    DATABASE_URL - PostgreSQL connection string (reads from .env if not set)
"""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import AsyncSessionLocal
from app.models.working_hour import WorkingHour
from app.models.master_profile import MasterProfile
from datetime import date, timedelta


async def fix_masters(session):
    """Add working hours to masters with 0 active days."""
    print("\n👨‍🔧 Checking master working hours...")
    
    from sqlalchemy import select, func
    
    # Find masters with 0 active working days
    result = await session.execute(
        select(WorkingHour.master_id, func.count(WorkingHour.id).label("wh_count"))
        .where(WorkingHour.is_active == True)
        .group_by(WorkingHour.master_id)
    )
    masters_with_wh = {row[0]: row[1] for row in result.all()}
    
    # Get all master profiles
    mp_result = await session.execute(select(MasterProfile))
    all_masters = mp_result.scalars().all()
    
    fixed_count = 0
    today = date.today()
    
    for mp in all_masters:
        wh_count = masters_with_wh.get(mp.id, 0)
        if wh_count == 0:
            print(f"  Master {mp.id} has 0 working days — adding 5 days")
            for i in range(5):
                wh = WorkingHour(
                    master_id=mp.id,
                    schedule_date=today + timedelta(days=i),
                    start_time="09:00:00",
                    end_time="18:00:00",
                    is_active=True,
                )
                session.add(wh)
                fixed_count += 1
    
    if fixed_count == 0:
        print("  ✓ All masters already have working hours")
    else:
        await session.commit()
        print(f"  ✓ Added {fixed_count} working hours for {fixed_count // 5} master(s)")


async def main():
    print("Fixing master working hours...")
    
    async with AsyncSessionLocal() as session:
        await fix_masters(session)
        
        print("\n" + "="*60)
        print("✅ Master working hours fix applied!")
        print("="*60)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import time
from app.database import get_db
from app.models.working_hour import WorkingHour
from app.schemas.working_hour import WorkingHourCreate, WorkingHourResponse

router = APIRouter()

@router.get("/", response_model=List[WorkingHourResponse])
async def get_working_hours(master_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkingHour).where(WorkingHour.master_id == master_id))
    working_hours = result.scalars().all()
    return working_hours

@router.post("/", response_model=WorkingHourResponse, status_code=201)
async def create_working_hour(wh: WorkingHourCreate, db: AsyncSession = Depends(get_db)):
    # Convert string times to time objects
    start_time = time.fromisoformat(wh.start_time)
    end_time = time.fromisoformat(wh.end_time)
    
    new_wh = WorkingHour(
        master_id=wh.master_id,
        schedule_date=wh.schedule_date,
        start_time=start_time,
        end_time=end_time
    )
    
    db.add(new_wh)
    await db.commit()
    await db.refresh(new_wh)
    return new_wh

@router.delete("/{wh_id}", status_code=204)
async def delete_working_hour(wh_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkingHour).where(WorkingHour.id == wh_id))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Working hour not found")
    await db.delete(wh)
    await db.commit()
    return None

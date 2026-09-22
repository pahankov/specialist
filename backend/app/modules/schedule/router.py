"""Schedule module — working hours CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import time

from app.database import get_db
from app.models.working_hour import WorkingHour
from app.schemas.working_hour import WorkingHourCreate
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


def _working_hour_to_dict(wh):
    return {
        "id": wh.id,
        "master_id": wh.master_id,
        "schedule_date": wh.schedule_date.isoformat() if wh.schedule_date else None,
        "start_time": wh.start_time.isoformat() if wh.start_time else None,
        "end_time": wh.end_time.isoformat() if wh.end_time else None,
    }


@router.get("/", response_model=List[dict])
async def get_working_hours(master_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkingHour).where(WorkingHour.master_id == master_id))
    working_hours = result.scalars().all()
    return [_working_hour_to_dict(wh) for wh in working_hours]


@router.post("/", response_model=dict, status_code=201)
async def create_working_hour(wh: WorkingHourCreate, db: AsyncSession = Depends(get_db)):
    start_time_obj = time.fromisoformat(wh.start_time)
    end_time_obj = time.fromisoformat(wh.end_time)

    new_wh = WorkingHour(
        master_id=wh.master_id,
        schedule_date=wh.schedule_date,
        start_time=start_time_obj,
        end_time=end_time_obj
    )

    db.add(new_wh)
    await db.commit()
    await db.refresh(new_wh)
    return _working_hour_to_dict(new_wh)


@router.delete("/{wh_id}", status_code=204)
async def delete_working_hour(wh_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(WorkingHour).where(WorkingHour.id == wh_id))
    wh = result.scalar_one_or_none()
    if not wh:
        raise HTTPException(status_code=404, detail="Working hour not found")
    await db.delete(wh)
    await db.commit()
    return None

"""Schedule module — working hours CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from datetime import time

from app.database import get_db
from app.models.working_hour import WorkingHour
from app.models.user import User
from app.schemas.working_hour import WorkingHourCreate
from app.dependencies.auth import require_master
from app.dependencies.crud import get_owned_or_404
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
async def get_working_hours(
    master: User = Depends(require_master),
    master_id: int = None,
    db: AsyncSession = Depends(get_db)
):
    """Get working hours for the authenticated master (or specified master for superadmin)."""
    is_admin = master.role == "ADMIN"
    
    if is_admin and master_id is not None:
        query = select(WorkingHour).where(WorkingHour.master_id == master_id)
    else:
        query = select(WorkingHour).where(WorkingHour.master_id == master.master_profile.id)
    
    result = await db.execute(query)
    working_hours = result.scalars().all()
    return [_working_hour_to_dict(wh) for wh in working_hours]


@router.post("/", response_model=dict, status_code=201)
async def create_working_hour(
    wh: WorkingHourCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create working hours for the authenticated master."""
    # Verify the master_id matches the authenticated user
    if wh.master_id != master.master_profile.id:
        raise HTTPException(status_code=403, detail="Cannot create working hours for another master")
    
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
async def delete_working_hour(
    wh_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete working hour (only if owned by the authenticated master)."""
    hour = await get_owned_or_404(db, WorkingHour, wh_id, master.master_profile.id)
    await db.delete(hour)
    await db.commit()
    return None

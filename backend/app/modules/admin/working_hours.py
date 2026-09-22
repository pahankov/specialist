"""Admin working hours CRUD endpoints."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from datetime import time
from app.modules.admin.base import (
    get_db, WorkingHour, Master, require_master, get_owned_or_404, log_action,
    WorkingHourCreate, WorkingHourUpdate, WorkingHourResponse
)

router = APIRouter()


@router.get("/working-hours", response_model=List[WorkingHourResponse])
async def get_working_hours(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get working hours for the authenticated master."""
    result = await db.execute(
        select(WorkingHour).where(WorkingHour.master_id == master.id)
        .order_by(WorkingHour.schedule_date)
    )
    return result.scalars().all()


@router.post("/working-hours", response_model=WorkingHourResponse, status_code=201)
async def create_working_hour(
    data: WorkingHourCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create working hours."""
    hour = WorkingHour(
        master_id=master.id, schedule_date=data.schedule_date,
        start_time=data.start_time,
        end_time=data.end_time
    )
    db.add(hour)
    await db.flush()
    await db.refresh(hour)
    await log_action(db, master.id, "create", "working_hour", hour.id, f"{data.schedule_date}: {data.start_time}-{data.end_time}", level="info")
    await db.commit()
    return hour


@router.patch("/working-hours/{hour_id}", response_model=WorkingHourResponse)
async def update_working_hour(
    hour_id: int,
    data: WorkingHourUpdate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update working hours."""
    hour = await get_owned_or_404(db, WorkingHour, hour_id, master.id)
    changes = []
    if data.schedule_date is not None:
        hour.schedule_date = data.schedule_date
        changes.append(f"дата: {data.schedule_date}")
    if data.start_time is not None:
        hour.start_time = data.start_time
        changes.append(f"начало: {data.start_time}")
    if data.end_time is not None:
        hour.end_time = data.end_time
        changes.append(f"конец: {data.end_time}")
    await log_action(db, master.id, "update", "working_hour", hour_id, ", ".join(changes) if changes else "Обновление", level="info")
    await db.commit()
    await db.refresh(hour)
    return hour


@router.delete("/working-hours/{hour_id}", status_code=204)
async def delete_working_hour(
    hour_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete working hours."""
    hour = await get_owned_or_404(db, WorkingHour, hour_id, master.id)
    await log_action(db, master.id, "delete", "working_hour", hour_id, f"{hour.schedule_date}: {hour.start_time}-{hour.end_time}", level="warning")
    await db.delete(hour)
    await db.commit()
    return None

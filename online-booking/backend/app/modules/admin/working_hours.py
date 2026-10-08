"""Admin working hours CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import time

from app.database import get_db
from app.models.working_hour import WorkingHour
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.schemas.working_hour import WorkingHourCreate, WorkingHourUpdate, WorkingHourResponse
from app.dependencies.auth import require_master
from app.dependencies.crud import get_owned_or_404, get_or_404
from app.services.audit import log_action
from app.services.master_status import update_master_status_from_working_hours
from app.modules.admin.helpers import get_master_profile_id
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/working-hours", response_model=List[WorkingHourResponse])
async def get_working_hours(
    master: User = Depends(require_master),
    master_id: Optional[int] = Query(None, description="Filter by master ID (superadmin only)"),
    db: AsyncSession = Depends(get_db)
):
    """Get working hours for the authenticated master (or specified master for superadmin)."""
    logger.info("Get working hours: master=%s, master_id=%s", master.id, master_id)
    is_admin = master.role == "ADMIN"
    
    if is_admin and master_id is not None:
        query = select(WorkingHour).where(WorkingHour.master_id == master_id).order_by(WorkingHour.schedule_date)
    else:
        mp_id = await get_master_profile_id(db, master)
        query = select(WorkingHour).where(WorkingHour.master_id == mp_id).order_by(WorkingHour.schedule_date)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/working-hours", response_model=WorkingHourResponse, status_code=201)
async def create_working_hour(
    data: WorkingHourCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create working hours.

    Regular master: always for themselves. Superadmin: MUST pass
    data.master_id (target MasterProfile.id) — superadmins have no
    profile of their own, "adding to self" is rejected with 400.
    """
    if master.role == UserRole.ADMIN:
        if data.master_id is None:
            raise HTTPException(
                status_code=400,
                detail="Укажите мастера (master_id): суперпользователь не может добавить часы себе",
            )
        target = await db.execute(
            select(MasterProfile).where(MasterProfile.id == data.master_id)
        )
        if target.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Мастер не найден")
        mp_id = data.master_id
    else:
        mp_id = await get_master_profile_id(db, master)
    hour = WorkingHour(
        master_id=mp_id, schedule_date=data.schedule_date,
        start_time=data.start_time,
        end_time=data.end_time
    )
    db.add(hour)
    await db.flush()
    await db.refresh(hour)
    await log_action(db, master.id, "create", "working_hour", hour.id, f"{data.schedule_date}: {data.start_time}-{data.end_time}", level="info")
    await db.commit()
    
    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()
    
    return hour


@router.patch("/working-hours/{hour_id}", response_model=WorkingHourResponse)
async def update_working_hour(
    hour_id: int,
    data: WorkingHourUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update working hours (superadmin: any hour; master: own only)."""
    if master.role == UserRole.ADMIN:
        hour = await get_or_404(db, WorkingHour, hour_id)
    else:
        mp_id = await get_master_profile_id(db, master)
        hour = await get_owned_or_404(db, WorkingHour, hour_id, mp_id)
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
    if data.is_active is not None:
        hour.is_active = data.is_active
        changes.append(f"активность: {data.is_active}")
    await log_action(db, master.id, "update", "working_hour", hour_id, ", ".join(changes) if changes else "Обновление", level="info")
    await db.commit()
    await db.refresh(hour)
    
    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()
    
    return hour


@router.delete("/working-hours/{hour_id}", status_code=204)
async def delete_working_hour(
    hour_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete working hours (superadmin: any hour; master: own only)."""
    if master.role == UserRole.ADMIN:
        hour = await get_or_404(db, WorkingHour, hour_id)
    else:
        mp_id = await get_master_profile_id(db, master)
        hour = await get_owned_or_404(db, WorkingHour, hour_id, mp_id)
    await log_action(db, master.id, "delete", "working_hour", hour_id, f"{hour.schedule_date}: {hour.start_time}-{hour.end_time}", level="warning")
    await db.delete(hour)
    await db.commit()
    
    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()
    
    return None


@router.post("/working-hours/{hour_id}/toggle-active", response_model=WorkingHourResponse)
async def toggle_working_hour_active(
    hour_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Toggle working hour active/inactive status (superadmin: any hour)."""
    if master.role == UserRole.ADMIN:
        hour = await get_or_404(db, WorkingHour, hour_id)
    else:
        mp_id = await get_master_profile_id(db, master)
        hour = await get_owned_or_404(db, WorkingHour, hour_id, mp_id)
    hour.is_active = not hour.is_active
    await db.commit()
    await db.refresh(hour)
    
    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()
    
    return hour

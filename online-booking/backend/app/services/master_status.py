"""Master status management service.

Handles master status (active/inactive/suspended) and auto-detection
based on working hours.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.models.master_profile import MasterProfile, MasterStatus
from app.models.working_hour import WorkingHour
from app.services.audit import log_action


async def get_master_status(db: AsyncSession, master_profile: MasterProfile) -> MasterStatus:
    """Get current master status.
    
    If master is suspended → SUSPENDED
    If master has at least one active working day → ACTIVE
    Otherwise → INACTIVE (auto-detected)
    """
    if master_profile.status == MasterStatus.SUSPENDED:
        return MasterStatus.SUSPENDED
    
    # Check for active working days
    result = await db.execute(
        select(func.count(WorkingHour.id))
        .where(
            WorkingHour.master_id == master_profile.id,
            WorkingHour.is_active == True
        )
    )
    active_days_count = result.scalar() or 0
    
    return MasterStatus.ACTIVE if active_days_count > 0 else MasterStatus.INACTIVE


async def set_master_status(
    db: AsyncSession,
    master_profile: MasterProfile,
    new_status: MasterStatus,
    admin_master_id: int
) -> MasterStatus:
    """Set master status and log the action."""
    old_status = master_profile.status
    master_profile.status = new_status
    await db.flush()
    await log_action(
        db, admin_master_id, "update", "master_status",
        master_profile.id,
        f"Статус: {old_status.value} → {new_status.value}"
    )
    return new_status


async def update_master_status_from_working_hours(
    db: AsyncSession,
    master_profile: MasterProfile
) -> MasterStatus:
    """Auto-update master status based on working hours.
    
    If master has active working days → ACTIVE
    Otherwise → INACTIVE (only if not suspended)
    """
    if master_profile.status == MasterStatus.SUSPENDED:
        return MasterStatus.SUSPENDED
    
    result = await db.execute(
        select(func.count(WorkingHour.id))
        .where(
            WorkingHour.master_id == master_profile.id,
            WorkingHour.is_active == True
        )
    )
    active_days_count = result.scalar() or 0
    
    new_status = MasterStatus.ACTIVE if active_days_count > 0 else MasterStatus.INACTIVE
    
    if master_profile.status != new_status:
        master_profile.status = new_status
        await db.flush()
    
    return new_status

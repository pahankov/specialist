"""Shared helpers for admin module."""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.appointment import Appointment
from app.dependencies.crud import get_owned_or_404, get_or_404


async def get_appointment_for_master(
    db: AsyncSession,
    appointment_id: int,
    master: User
):
    """Get appointment for master — handles both admin and regular master.
    
    - Admin: returns appointment by ID (global access)
    - Regular master: returns appointment if owned by master
    """
    is_admin = master.role == UserRole.ADMIN
    
    if not is_admin:
        result = await db.execute(
            select(MasterProfile).where(MasterProfile.user_id == master.id)
        )
        mp = result.scalar_one_or_none()
        if not mp:
            raise HTTPException(status_code=403, detail="Not a master")
        
        return await get_owned_or_404(db, Appointment, appointment_id, mp.id)
    else:
        return await get_or_404(db, Appointment, appointment_id)

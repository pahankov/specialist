"""Shared helpers for admin module."""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.client_profile import ClientProfile
from app.models.appointment import Appointment
from app.dependencies.crud import get_owned_or_404, get_or_404


async def get_master_profile_id(db: AsyncSession, master: User) -> int:
    """Get master_profile.id safely — handles both admin and regular master.
    
    - Admin (role=ADMIN): returns master.id (User.id) — admin has no MasterProfile
    - Regular master: returns master_profile.id
    - Non-master: raises 403
    """
    if master.role == UserRole.ADMIN:
        return master.id
    result = await db.execute(select(MasterProfile).where(MasterProfile.user_id == master.id))
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=403, detail="Not a master")
    return mp.id


async def own_client_user_ids(db: AsyncSession, master: User) -> set:
    """User ids of a regular master's OWN clients.

    Own = booked at least once with this master OR created by this
    master (ClientsPage "+ Добавить клиента" stamps created_by),
    MINUS clients the master hid from their lists.
    Superadmin must not call this (sees everyone).
    """
    from app.models.master_hidden_client import MasterHiddenClient

    mp_id = await get_master_profile_id(db, master)
    booked = await db.execute(
        select(ClientProfile.user_id)
        .join(Appointment, Appointment.client_id == ClientProfile.id)
        .where(Appointment.master_id == mp_id)
    )
    created = await db.execute(
        select(User.id).where(User.created_by == master.id)
    )
    hidden_cp = await db.execute(
        select(MasterHiddenClient.client_profile_id).where(
            MasterHiddenClient.master_profile_id == mp_id)
    )
    hidden_cp_ids = [r[0] for r in hidden_cp.all()]
    hidden: set = set()
    if hidden_cp_ids:
        hidden_rows = await db.execute(
            select(ClientProfile.user_id).where(
                ClientProfile.id.in_(hidden_cp_ids))
        )
        hidden = {r[0] for r in hidden_rows.all()}
    return ({r[0] for r in booked.all()} | {r[0] for r in created.all()}) - hidden


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

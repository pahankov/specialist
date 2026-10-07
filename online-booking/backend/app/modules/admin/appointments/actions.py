"""Admin appointment status actions: confirm / cancel / complete / delete / no-show."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.client_profile import ClientProfile
from app.models.user import User
from app.dependencies.auth import require_master
from app.modules.admin.helpers import get_appointment_for_master
from app.services.audit import log_action
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.patch("/appointments/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Confirm an appointment."""
    logger.info("Confirm appointment %s by master %s", appointment_id, master.id)
    appointment = await get_appointment_for_master(db, appointment_id, master)
    appointment.status = "confirmed"
    await log_action(db, master.id, "confirm", "appointment", appointment.id, "Статус изменён на confirmed", level="info")
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.patch("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    reason: Optional[str] = Query(None),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an appointment."""
    logger.info("Cancel appointment %s by master %s, reason=%s", appointment_id, master.id, reason)
    appointment = await get_appointment_for_master(db, appointment_id, master)
    appointment.status = "cancelled"
    if reason:
        appointment.notes = f"{appointment.notes}\nОтмена: {reason}" if appointment.notes else f"Отмена: {reason}"
    await log_action(db, master.id, "cancel", "appointment", appointment.id, f"Причина: {reason}", level="warning")
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.patch("/appointments/{appointment_id}/complete")
async def complete_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Mark an appointment as completed."""
    logger.info("Complete appointment %s by master %s", appointment_id, master.id)
    appointment = await get_appointment_for_master(db, appointment_id, master)
    appointment.status = "completed"
    await log_action(db, master.id, "complete", "appointment", appointment.id, level="info")
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.delete("/appointments/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete an appointment."""
    logger.info("Delete appointment %s by master %s", appointment_id, master.id)
    appointment = await get_appointment_for_master(db, appointment_id, master)
    await log_action(db, master.id, "delete", "appointment", appointment_id, level="warning")
    await db.delete(appointment)
    await db.commit()
    return None


@router.patch("/appointments/{appointment_id}/no-show")
async def mark_no_show(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Mark an appointment as no-show. Increments client's no_show_count."""
    logger.info("No-show appointment %s by master %s", appointment_id, master.id)
    appointment = await get_appointment_for_master(db, appointment_id, master)
    appointment.status = "cancelled"
    appointment.notes = f"{appointment.notes}\n\nНеявка" if appointment.notes else "Неявка"
    await log_action(db, master.id, "no-show", "appointment", appointment_id, level="warning")

    if appointment.client_id:
        client_result = await db.execute(
            select(ClientProfile).where(ClientProfile.user_id == appointment.client_id)
        )
        client = client_result.scalar_one_or_none()
        if client:
            client.no_show_count = (client.no_show_count or 0) + 1

    await db.commit()
    await db.refresh(appointment)
    return appointment

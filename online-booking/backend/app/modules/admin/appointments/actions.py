"""Admin appointment status actions: confirm / cancel / complete / delete / no-show."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.user import User
from app.dependencies.auth import require_master
from app.modules.admin.helpers import get_appointment_for_master
from app.services.audit import log_action
from app.services.booking import format_slot
from app.services.notifications import notify_user
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _bell_client(
    db: AsyncSession, appointment: Appointment, master: User, verb: str,
    extra: str = "",
) -> None:
    """Notify the appointment's client (profile id; legacy rows may hold one).

    Best-effort: never breaks the status change itself.
    """
    try:
        full = (await db.execute(
            select(Appointment)
            .options(
                selectinload(Appointment.client_profile).joinedload(ClientProfile.user),
                selectinload(Appointment.service),
            )
            .where(Appointment.id == appointment.id)
        )).scalar_one_or_none()
        if full is None:
            return
        cp = full.client_profile
        if cp is None:
            legacy = (await db.execute(
                select(ClientProfile).where(ClientProfile.user_id == appointment.client_id)
            )).scalar_one_or_none()
            cp = legacy
        if cp is None:
            return
        service_name = full.service.name if full.service else "услуга"
        text = (f"{master.name}: {verb} запись: "
                f"{service_name}, {format_slot(appointment.appointment_date)}")
        if extra:
            text += f" ({extra})"
        await notify_user(
            db, recipient_id=cp.user_id, text=text,
            sender_id=master.id, audience="booking",
            link=f"appointments:{appointment.id}",
        )
    except Exception as e:
        logger.warning("Bell to client failed (non-fatal): %s", e)


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
    await _bell_client(db, appointment, master, "подтвердил(а)")
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
    await _bell_client(db, appointment, master, "отменил(а)",
                       extra=f"причина: {reason}" if reason else "")
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


@router.patch("/appointments/{appointment_id}/reopen")
async def reopen_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Return a completed appointment to work (e.g. auto-complete misfired).

    Back to confirmed: no-show or cancel-with-reason work from there.
    """
    logger.info("Reopen appointment %s by master %s", appointment_id, master.id)
    appointment = await get_appointment_for_master(db, appointment_id, master)
    if appointment.status != "completed":
        raise HTTPException(status_code=400, detail="Вернуть в работу можно только завершённую")
    appointment.status = "confirmed"
    await log_action(db, master.id, "reopen", "appointment", appointment.id, level="info")
    await _bell_client(db, appointment, master, "вернул(а) в работу")
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
            select(ClientProfile).where(ClientProfile.id == appointment.client_id)
        )
        client = client_result.scalar_one_or_none()
        if client is None:
            # Legacy rows (pre-1.23.3) stored users.id in client_id.
            legacy = await db.execute(
                select(ClientProfile).where(ClientProfile.user_id == appointment.client_id)
            )
            client = legacy.scalar_one_or_none()
        if client:
            client.no_show_count = (client.no_show_count or 0) + 1

    await db.commit()
    await db.refresh(appointment)
    return appointment

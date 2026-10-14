"""Auto-complete: confirmed bookings whose end passed flip to completed.

Only for masters with MasterProfile.auto_complete on. Runs as a lifespan
background loop (no extra deps); manual complete/cancel keep working —
a master can still cancel an auto-completed row.
"""
import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.services.booking import format_slot
from app.services.notifications import notify_user
from app.utils import utcnow_naive

logger = get_logger(__name__)

INTERVAL_SECONDS = 10 * 60


async def run_auto_complete_once(session_factory=None) -> int:
    """Complete eligible rows once. Returns the completed count."""
    now = utcnow_naive()
    done = 0
    factory = session_factory or AsyncSessionLocal
    async with factory() as db:
        rows = (await db.execute(
            select(Appointment, MasterProfile)
            .join(MasterProfile, Appointment.master_id == MasterProfile.id)
            .where(Appointment.status == "confirmed",
                   MasterProfile.auto_complete == True)  # noqa: E712
        )).all()
        for appt, mp in rows:
            dur = appt.duration_minutes or 60
            try:
                end = appt.appointment_date + timedelta(minutes=int(dur))
            except Exception:
                continue
            if end > now:
                continue
            appt.status = "completed"
            done += 1
            try:
                cp = (await db.execute(
                    select(ClientProfile).where(
                        ClientProfile.id == appt.client_id)
                )).scalar_one_or_none()
                if cp is not None:
                    label = appt.bundle_name or "запись"
                    if appt.service_id:
                        from app.models.service import Service
                        sname = (await db.execute(
                            select(Service.name).where(Service.id == appt.service_id)
                        )).scalar_one_or_none()
                        if sname:
                            label = sname
                    await notify_user(
                        db, recipient_id=cp.user_id,
                        text=(f"Услуга завершена: {label}, "
                              f"{format_slot(appt.appointment_date)} — "
                              f"оцените визит в Истории ⭐"),
                        audience="booking", link="appointments",
                    )
            except Exception as e:
                logger.warning("Auto-complete bell failed (non-fatal): %s", e)
        if done:
            await db.commit()
            logger.info("Auto-complete: %s appointment(s) completed", done)
    return done


async def auto_complete_loop() -> None:
    """Lifespan loop: sweep every INTERVAL_SECONDS, never crash the app."""
    while True:
        try:
            await run_auto_complete_once()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.warning("Auto-complete sweep failed (non-fatal): %s", e)
        await asyncio.sleep(INTERVAL_SECONDS)

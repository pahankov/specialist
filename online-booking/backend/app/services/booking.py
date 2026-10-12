"""Exact appointment overlap check (both sides' own durations).

Replaces the old approximation (existing.start + NEW.duration > new.start),
which missed overlaps when the existing booking was longer than the new one.
"""
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.service import Service


async def find_conflict(
    db: AsyncSession,
    master_profile_id: int,
    start_naive: datetime,
    duration_minutes: int,
) -> Appointment | None:
    """First live appointment overlapping [start, start+duration), if any."""
    end = start_naive + timedelta(minutes=duration_minutes)
    candidates = (await db.execute(
        select(Appointment, Service.duration_minutes)
        .join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.master_id == master_profile_id,
            Appointment.status != "cancelled",
            Appointment.appointment_date < end,
        )
    )).all()
    for existing, dur in candidates:
        existing_start = existing.appointment_date.replace(tzinfo=None)
        if existing_start + timedelta(minutes=dur or 0) > start_naive:
            return existing
    return None


def format_slot(dt) -> str:
    """Human slot for bell texts: '14.10 в 14:00'."""
    d = dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
    return d.strftime("%d.%m в %H:%M")

"""Exact appointment overlap check (both sides' own durations).

Replaces the old approximation (existing.start + NEW.duration > new.start),
which missed overlaps when the existing booking was longer than the new one.
"""
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.appointment import Appointment
from app.models.service import Service
from app.models.service_bundle import ServiceBundle


async def find_conflict(
    db: AsyncSession,
    master_profile_id: int,
    start_naive: datetime,
    duration_minutes: int,
) -> Appointment | None:
    """First live appointment overlapping [start, start+duration), if any."""
    end = start_naive + timedelta(minutes=duration_minutes)
    # Bundle rows have service_id=NULL: outer join + duration snapshot.
    candidates = (await db.execute(
        select(Appointment,
               func.coalesce(Service.duration_minutes,
                             Appointment.duration_minutes))
        .outerjoin(Service, Appointment.service_id == Service.id)
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


async def resolve_booking_item(
    db: AsyncSession,
    master_profile_id: int,
    service_id: int | None = None,
    bundle_id: int | None = None,
) -> dict:
    """Exactly one of service_id / bundle_id. Returns booking facts.

    Service: live service row. Bundle: active own complex; duration = sum,
    price = custom or sum; every member must exist + be active right now.
    Snapshots (bundle_name/duration/price) are returned for the appointment.
    """
    if (service_id is None) == (bundle_id is None):
        raise HTTPException(
            status_code=400,
            detail="Укажите услугу или комплекс (ровно один)",
        )
    if bundle_id is not None:
        b = (await db.execute(
            select(ServiceBundle).where(ServiceBundle.id == bundle_id,
                                        ServiceBundle.master_id == master_profile_id)
        )).scalar_one_or_none()
        if b is None or b.is_active is False:
            raise HTTPException(status_code=404, detail="Комплекс не найден")
        members = (await db.execute(
            select(Service).where(Service.id.in_(b.service_ids or []),
                                  Service.master_id == master_profile_id)
        )).scalars().all()
        if len(members) != len(b.service_ids or []) or \
                any(s.is_active is False for s in members):
            raise HTTPException(
                status_code=400,
                detail="Комплекс изменился — попросите мастера обновить его",
            )
        from app.modules.admin.bundles import bundle_total_minutes, effective_durations
        from app.services.pricing import apply_discount
        overrides = effective_durations(b)
        duration = bundle_total_minutes(
            b, sum(overrides.get(s.id, s.duration_minutes or 0)
                   for s in members))
        members_effective = round(sum(m.effective_price for m in members), 2)
        base = float(b.price) if b.price is not None else members_effective
        price = apply_discount(base, b.discount_percent, b.discount_until)
        return {
            "service_id": None, "bundle_id": b.id, "bundle_name": b.name,
            "name": b.name, "duration_minutes": duration, "price": price,
        }
    service = (await db.execute(
        select(Service).where(Service.id == service_id,
                              Service.master_id == master_profile_id)
    )).scalar_one_or_none()
    if service is None or service.is_active is False:
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    return {
        "service_id": service.id, "bundle_id": None, "bundle_name": None,
        "name": service.name, "duration_minutes": service.duration_minutes,
        "price": service.effective_price,
    }


def format_slot(dt) -> str:
    """Human slot for bell texts: '14.10 в 14:00'."""
    d = dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt
    return d.strftime("%d.%m в %H:%M")

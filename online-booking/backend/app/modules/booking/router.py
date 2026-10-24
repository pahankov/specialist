"""Booking module — appointment CRUD and public booking."""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.middleware.rate_limit import limiter
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.client_profile import ClientProfile
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.schemas.appointment import AppointmentCreate, AppointmentResponse, PublicBookingCreate, AvailableDay, AvailableSlot
from app.logging_config import get_logger
from app.dependencies.auth import require_master
from app.services.names import name_fields
from app.utils import localnow_naive

logger = get_logger(__name__)

router = APIRouter()


# ─── Response schemas ─────────────────────────────────────────────────
# Using schemas from app.schemas.appointment


# ─── Authenticated endpoints (require master) ─────────────────────────

@router.get("/", response_model=List[AppointmentResponse])
async def get_appointments(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments for the authenticated master."""
    logger.info("Запрос списка записей мастером id=%s", master.master_profile.id)
    result = await db.execute(
        select(Appointment).where(Appointment.master_id == master.master_profile.id)
    )
    appointments = result.scalars().all()
    logger.info("Найдено %d записей для мастера id=%s", len(appointments), master.master_profile.id)
    return appointments


@router.post("/", response_model=AppointmentResponse, status_code=201)
@limiter.limit("30/minute")
async def create_appointment(
    request: Request,
    appointment: AppointmentCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create appointment (authenticated master only)."""
    logger.info("Создание записи мастером id=%s: клиент=%s, время=%s",
                master.master_profile.id, appointment.client_phone, appointment.appointment_date)

    if appointment.master_id != master.master_profile.id:
        logger.warning("Попытка создать чужую запись: мастер=%s, запрошенный=%s",
                       master.master_profile.id, appointment.master_id)
        raise HTTPException(status_code=403, detail="Not your master")

    # Lock the master and validate the service + time before touching users.
    from app.services.booking import find_conflict, resolve_booking_item
    mp = (await db.execute(
        select(MasterProfile).where(MasterProfile.id == appointment.master_id)
        .with_for_update()
    )).scalar_one_or_none()
    if mp is None or mp.user_id != master.id:
        raise HTTPException(status_code=403, detail="Not your master")
    appt_dt = appointment.appointment_date.replace(tzinfo=None)
    item = await resolve_booking_item(db, mp.id, appointment.service_id)
    if await find_conflict(db, mp.id, appt_dt, item["duration_minutes"]):
        raise HTTPException(status_code=409, detail="Это время уже занято")

    # Check or create client. A dual-role master booking by own phone
    # reuses their account (profile attached on the fly) instead of
    # cloning a second user row for the same phone number.
    from app.utils.phone import normalize_phone
    try:
        lookup_phone = normalize_phone(appointment.client_phone)
    except ValueError:
        lookup_phone = appointment.client_phone
    client_result = await db.execute(
        select(ClientProfile).join(ClientProfile.user).where(User.phone == lookup_phone)
    )
    client = client_result.scalar_one_or_none()
    if client is None:
        owner = (await db.execute(
            select(User).where(User.phone == lookup_phone)
        )).scalar_one_or_none()
        if owner is not None:
            from app.services.clients import get_or_create_profile
            client = await get_or_create_profile(db, owner)

    if not client:
        logger.info("Создание нового клиента для записи: %s", appointment.client_phone)
        full_name, last_name = name_fields(appointment.client_name)
        new_user = User(
            name=full_name,
            last_name=last_name,
            phone=appointment.client_phone,
            role=UserRole.CLIENT
        )
        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)

        from app.services.clients import get_or_create_profile
        client = await get_or_create_profile(db, new_user)

    # Create appointment with booking-time snapshots.
    new_appointment = Appointment(
        master_id=appointment.master_id,
        service_id=item["service_id"],
        client_id=client.id,
        duration_minutes=item["duration_minutes"],
        price=item["price"],
        discount_label=item.get("discount_label") or None,
        appointment_date=appt_dt,
        status="confirmed",
        created_by_role="master",
        created_by_user_id=master.id,
    )

    db.add(new_appointment)
    await db.commit()
    await db.refresh(new_appointment)

    logger.info("Запись создана: id=%s, мастер=%s", new_appointment.id, master.master_profile.id)
    return new_appointment


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete appointment (authenticated master only)."""
    logger.info("Удаление записи: id=%s, мастер=%s", appointment_id, master.master_profile.id)
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.master_id == master.master_profile.id
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        logger.warning("Запись не найдена: id=%s", appointment_id)
        raise HTTPException(status_code=404, detail="Appointment not found")

    await db.delete(appointment)
    await db.commit()
    logger.info("Запись успешно удалена: id=%s", appointment_id)
    return None


# ─── Public endpoints (no auth) ───────────────────────────────────────

@router.get("/available-days", response_model=List[AvailableDay])
async def get_available_days(
    master_id: int = Query(...),
    days_ahead: int = Query(14),
    db: AsyncSession = Depends(get_db)
):
    """Get available days for a master (next N days, excluding Sundays)."""
    logger.info("Запрос доступных дней: мастер=%s, дней=%s", master_id, days_ahead)
    available_days = []
    today = localnow_naive().date()

    for i in range(days_ahead):
        check_date = today + timedelta(days=i)
        if check_date.weekday() != 6:
            available_days.append({
                "date": check_date.isoformat(),
                "day_of_week": check_date.weekday()
            })

    return available_days


@router.get("/available-slots", response_model=List[AvailableSlot])
async def get_available_slots(
    master_id: int = Query(...),
    service_id: int = Query(...),
    date: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Get available time slots for a service on a given date.

    Uses the master's own work window (work_start_hour / work_end_hour)
    from MasterProfile instead of a hardcoded 10-18 range.
    """
    logger.info("Запрос слотов: мастер=%s, услуга=%s, дата=%s", master_id, service_id, date)

    service_result = await db.execute(select(Service).where(Service.id == service_id))
    service = service_result.scalar_one_or_none()

    if not service:
        logger.warning("Услуга не найдена: id=%s", service_id)
        raise HTTPException(status_code=404, detail="Service not found")

    # Read master's work window from profile (defaults 08:00-22:00)
    master_result = await db.execute(
        select(MasterProfile).where(MasterProfile.id == master_id)
    )
    master_profile = master_result.scalar_one_or_none()
    if master_profile is None:
        logger.warning("Мастер не найден: id=%s", master_id)
        raise HTTPException(status_code=404, detail="Master not found")

    start_hour = master_profile.work_start_hour if master_profile.work_start_hour is not None else 8
    end_hour = master_profile.work_end_hour if master_profile.work_end_hour is not None else 22

    slots = []
    appointment_datetime = datetime.fromisoformat(date)
    current_time = appointment_datetime.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end_time = appointment_datetime.replace(hour=end_hour, minute=0, second=0, microsecond=0)

    while current_time + timedelta(minutes=service.duration_minutes) <= end_time:
        slots.append({
            "start": current_time.isoformat(),
            "end": (current_time + timedelta(minutes=service.duration_minutes)).isoformat()
        })
        current_time = current_time + timedelta(hours=1)

    logger.info("Найдено %d слотов для даты %s", len(slots), date)
    return slots


@router.post("/public", response_model=AppointmentResponse, status_code=201)
@limiter.limit("10/minute")
async def public_booking(request: Request, booking: PublicBookingCreate, db: AsyncSession = Depends(get_db)):
    """Public booking — no auth required. Creates appointment for any master."""
    logger.info("Публичная запись: мастер=%s, клиент=%s, время=%s",
                booking.master_id, booking.client_phone, booking.appointment_date)

    # Verify master exists and is active
    master_result = await db.execute(
        select(MasterProfile).join(MasterProfile.user).where(
            MasterProfile.id == booking.master_id,
            MasterProfile.is_active == True,
            MasterProfile.status == "active",
            User.role == UserRole.MASTER,
        ).with_for_update()
    )
    master_profile = master_result.scalar_one_or_none()
    if not master_profile:
        logger.warning("Мастер не найден или неактивен: id=%s", booking.master_id)
        raise HTTPException(status_code=404, detail="Master not found or inactive")
    from app.services.billing import is_master_bookable
    if not await is_master_bookable(db, master_profile.id):
        raise HTTPException(status_code=404, detail="Master not found or inactive")

    # Verify service exists and belongs to master
    service_result = await db.execute(
        select(Service).where(
            Service.id == booking.service_id,
            Service.master_id == booking.master_id,
            Service.is_active == True
        )
    )
    service = service_result.scalar_one_or_none()
    if not service:
        logger.warning("Услуга не найдена: id=%s, мастер=%s", booking.service_id, booking.master_id)
        raise HTTPException(status_code=404, detail="Service not found or inactive")

    # Check for time conflicts (exact: each side's own duration)
    from app.services.booking import find_conflict, format_slot
    from app.services.notifications import notify_user
    if await find_conflict(db, booking.master_id,
                           booking.appointment_date.replace(tzinfo=None),
                           service.duration_minutes):
        logger.warning("Конфликт времени: мастер=%s, время=%s", booking.master_id, booking.appointment_date)
        raise HTTPException(status_code=409, detail="Это время уже занято")

    # Check or create client (normalize first: registration stores phones
    # as +7 (XXX) XXX-XX-XX, raw input would miss and clone the client).
    from app.utils.phone import normalize_phone
    try:
        lookup_phone = normalize_phone(booking.client_phone)
    except ValueError:
        lookup_phone = booking.client_phone
    client_result = await db.execute(
        select(ClientProfile).join(ClientProfile.user).where(User.phone == lookup_phone)
    )
    client = client_result.scalar_one_or_none()

    if not client:
        logger.info("Создание нового клиента для записи: %s", booking.client_phone)
        full_name, last_name = name_fields(booking.client_name)
        new_user = User(
            name=full_name,
            last_name=last_name,
            phone=booking.client_phone,
            role=UserRole.CLIENT
        )
        db.add(new_user)
        await db.flush()
        await db.refresh(new_user)

        from app.services.clients import get_or_create_profile
        client = await get_or_create_profile(db, new_user)
    else:
        # Anonymous entry point: a blacklisted phone sees the same generic
        # "unavailable" as an inactive master (no block disclosure).
        from app.services.client_visibility import is_client_blocked
        if await is_client_blocked(db, booking.master_id, client.id):
            raise HTTPException(status_code=404,
                                detail="Master not found or inactive")
        if client.user_id == master_profile.user_id:
            raise HTTPException(status_code=400,
                                detail="Нельзя записаться к самому себе")

    # Create appointment
    client_note = (booking.notes or "").strip()
    from app.services.pricing import discount_tag
    appointment = Appointment(
        master_id=booking.master_id,
        service_id=booking.service_id,
        client_id=client.id,
        appointment_date=booking.appointment_date,
        status="confirmed" if master_profile.auto_confirm else "pending",
        duration_minutes=service.duration_minutes,
        price=service.effective_price,
        discount_label=discount_tag(service.discount_percent,
                                    service.discount_fixed,
                                    service.discount_until) or None,
        notes=client_note or None,
        created_by_role="public",
    )

    db.add(appointment)
    await db.flush()
    await notify_user(
        db, recipient_id=master_profile.user_id,
        text=f"Новая запись: {booking.client_name} — "
             f"{service.name}, {format_slot(booking.appointment_date)}"
             + (f" — «{client_note[:120]}»" if client_note else ""),
        sender_id=client.user_id, audience="booking",
        link=f"appointments:{appointment.id}",
    )
    await db.commit()
    await db.refresh(appointment)

    logger.info("Публичная запись создана: id=%s, мастер=%s", appointment.id, booking.master_id)
    return appointment

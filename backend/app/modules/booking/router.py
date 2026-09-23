"""Booking module — appointment CRUD and public booking."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.database import get_db
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.client import Client
from app.models.master import Master
from app.schemas.appointment import AppointmentCreate, AppointmentResponse, PublicBookingCreate, AvailableDay, AvailableSlot
from app.logging_config import get_logger
from app.modules.auth.dependencies import require_master

logger = get_logger(__name__)

router = APIRouter()


# ─── Response schemas ─────────────────────────────────────────────────
# Using schemas from app.schemas.appointment


# ─── Authenticated endpoints (require master) ─────────────────────────

@router.get("/", response_model=List[AppointmentResponse])
async def get_appointments(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments for the authenticated master."""
    logger.info("Запрос списка записей мастером id=%s", master.id)
    result = await db.execute(
        select(Appointment).where(Appointment.master_id == master.id)
    )
    appointments = result.scalars().all()
    logger.info("Найдено %d записей для мастера id=%s", len(appointments), master.id)
    return appointments


@router.post("/", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    appointment: AppointmentCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create appointment (authenticated master only)."""
    logger.info("Создание записи мастером id=%s: клиент=%s, время=%s",
                master.id, appointment.client_phone, appointment.appointment_date)

    if appointment.master_id != master.id:
        logger.warning("Попытка создать чужую запись: мастер=%s, запрошенный=%s",
                       master.id, appointment.master_id)
        raise HTTPException(status_code=403, detail="Not your master")

    # Check or create client
    client_result = await db.execute(select(Client).where(Client.phone == appointment.client_phone))
    client = client_result.scalar_one_or_none()

    if not client:
        logger.info("Создание нового клиента для записи: %s", appointment.client_phone)
        client = Client(
            name=appointment.client_name,
            phone=appointment.client_phone
        )
        db.add(client)
        await db.flush()
        await db.refresh(client)

    # Create appointment
    new_appointment = Appointment(
        master_id=appointment.master_id,
        service_id=appointment.service_id,
        client_id=client.id,
        appointment_date=appointment.appointment_date,
        status="confirmed"
    )

    db.add(new_appointment)
    await db.flush()
    await db.refresh(new_appointment)

    logger.info("Запись создана: id=%s, мастер=%s", new_appointment.id, master.id)
    return new_appointment


@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete appointment (authenticated master only)."""
    logger.info("Удаление записи: id=%s, мастер=%s", appointment_id, master.id)
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.master_id == master.id
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
    today = datetime.now().date()

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
    """Get available time slots for a service on a given date."""
    logger.info("Запрос слотов: мастер=%s, услуга=%s, дата=%s", master_id, service_id, date)

    service_result = await db.execute(select(Service).where(Service.id == service_id))
    service = service_result.scalar_one_or_none()

    if not service:
        logger.warning("Услуга не найдена: id=%s", service_id)
        raise HTTPException(status_code=404, detail="Service not found")

    slots = []
    appointment_datetime = datetime.fromisoformat(date)
    start_hour = 10
    end_hour = 18

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
async def public_booking(booking: PublicBookingCreate, db: AsyncSession = Depends(get_db)):
    """Public booking — no auth required. Creates appointment for any master."""
    logger.info("Публичная запись: мастер=%s, клиент=%s, время=%s",
                booking.master_id, booking.client_phone, booking.appointment_date)

    # Verify master exists and is active
    master_result = await db.execute(
        select(Master).where(Master.id == booking.master_id, Master.is_active == True)
    )
    master = master_result.scalar_one_or_none()
    if not master:
        logger.warning("Мастер не найден или неактивен: id=%s", booking.master_id)
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

    # Check for time conflicts
    service_end = booking.appointment_date + timedelta(minutes=service.duration_minutes)
    conflict_result = await db.execute(
        select(Appointment).where(
            Appointment.master_id == booking.master_id,
            Appointment.status != "cancelled",
            Appointment.appointment_date < service_end,
            Appointment.appointment_date + timedelta(minutes=service.duration_minutes) > booking.appointment_date
        ).limit(1)
    )
    if conflict_result.scalar_one_or_none():
        logger.warning("Конфликт времени: мастер=%s, время=%s", booking.master_id, booking.appointment_date)
        raise HTTPException(status_code=409, detail="Это время уже занято")

    # Check or create client
    client_result = await db.execute(select(Client).where(Client.phone == booking.client_phone))
    client = client_result.scalar_one_or_none()

    if not client:
        logger.info("Создание нового клиента для записи: %s", booking.client_phone)
        client = Client(
            name=booking.client_name,
            phone=booking.client_phone
        )
        db.add(client)
        await db.flush()
        await db.refresh(client)

    # Create appointment
    appointment = Appointment(
        master_id=booking.master_id,
        service_id=booking.service_id,
        client_id=client.id,
        appointment_date=booking.appointment_date,
        status="pending"
    )

    db.add(appointment)
    await db.flush()
    await db.refresh(appointment)

    logger.info("Публичная запись создана: id=%s, мастер=%s", appointment.id, booking.master_id)
    return appointment

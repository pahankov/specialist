"""Admin appointment creation: direct create + panel booking."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from datetime import timedelta

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.user import User, UserRole
from app.models.service import Service
from app.models.master_profile import MasterProfile
from app.schemas.appointment import AdminBookingCreate, AppointmentResponse, AppointmentCreate
from app.dependencies.auth import require_master
from app.services.audit import log_action
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _find_or_create_client(db: AsyncSession, phone: str, name: str) -> User:
    """Helper: find existing client by phone or create new one."""
    from app.schemas.client import normalize_phone
    normalized = normalize_phone(phone)
    result = await db.execute(select(User).where(User.phone == normalized))
    user = result.scalar_one_or_none()
    if not user:
        user = User(name=name, phone=normalized, role=UserRole.CLIENT)
        db.add(user)
        await db.flush()
        client_profile = ClientProfile(user_id=user.id)
        db.add(client_profile)
        await db.commit()
        await db.refresh(user)
    return user


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new appointment."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
    )
    mp = result.scalar_one_or_none()
    if not mp or data.master_id != mp.id:
        raise HTTPException(status_code=403, detail="Not your master")
    client = await _find_or_create_client(db, data.client_phone, data.client_name)
    new_appointment = Appointment(
        master_id=data.master_id, service_id=data.service_id, client_id=client.id,
        appointment_date=data.appointment_date, status="pending", notes=data.notes
    )
    db.add(new_appointment)
    await db.flush()
    await db.refresh(new_appointment)
    await log_action(db, master.id, "create", "appointment", new_appointment.id, f"Клиент: {client.name}", level="info")
    await db.commit()
    return new_appointment


@router.post("/appointments/book", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    data: AdminBookingCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Book an appointment from admin panel (select client from DB)."""
    logger.info("Admin booking appointment: master=%s, client=%s, service=%s, date=%s",
                master.id, data.client_id, data.service_id, data.appointment_date)
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=403, detail="Not a master")

    service_result = await db.execute(
        select(Service).where(Service.id == data.service_id, Service.master_id == mp.id)
    )
    service = service_result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    client_result = await db.execute(
        select(User).options(joinedload(User.client_profile)).where(User.id == data.client_id)
    )
    user = client_result.scalar_one_or_none()
    if not user or user.role.value != "CLIENT":
        raise HTTPException(status_code=404, detail="Клиент не найден")

    service_end = data.appointment_date + timedelta(minutes=service.duration_minutes)
    conflict_result = await db.execute(
        select(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.master_id == mp.id, Appointment.status != "cancelled",
            Appointment.appointment_date < service_end,
            Appointment.appointment_date + timedelta(minutes=service.duration_minutes) > data.appointment_date
        ).limit(1)
    )
    if conflict_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Это время уже занято")

    notes = "Запись из админ-панели"
    if data.notes:
        notes = f"{notes}. {data.notes}"

    new_appointment = Appointment(
        master_id=mp.id, service_id=data.service_id, client_id=user.client_profile.id,
        appointment_date=data.appointment_date, status=data.status, notes=notes
    )
    db.add(new_appointment)
    await db.commit()
    await db.refresh(new_appointment)
    return new_appointment

"""Client cabinet endpoints — own profile, own appointments, own cancel."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from typing import List

from app.database import get_db
from app.dependencies.auth import require_client
from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.city import City
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.service import Service
from app.models.user import User
from app.modules.client.schemas import (
    ClientMeResponse, ClientMeUpdate, ClientStatsResponse,
)
from app.schemas.appointment import AppointmentWithDetails
from app.services.audit import log_action
from app.utils import utcnow_naive

logger = get_logger(__name__)

router = APIRouter()

CANCELLABLE = ("pending", "confirmed")


async def _get_or_create_profile(db: AsyncSession, user: User) -> ClientProfile:
    """ClientProfile for the JWT user (created on the fly if missing)."""
    result = await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.info("Creating missing ClientProfile for user_id=%s", user.id)
        profile = ClientProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
    return profile


def _to_details(a: Appointment) -> dict:
    return {
        "id": a.id,
        "master_id": a.master_id,
        "service_id": a.service_id,
        "client_id": a.client_id,
        "appointment_date": a.appointment_date,
        "status": a.status,
        "notes": a.notes,
        "client_name": a.client_profile.user.name if a.client_profile else None,
        "client_phone": a.client_profile.user.phone if a.client_profile else None,
        "service_name": a.service.name if a.service else None,
        "service_price": a.service.price if a.service else None,
        "master_name": a.master_profile.user.name if a.master_profile else None,
    }


@router.get("/me", response_model=ClientMeResponse)
async def get_me(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Own profile (name/phone/city for the cabinet header)."""
    city_name = None
    if user.city_id:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == user.city_id)
        )).scalar_one_or_none()
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "is_verified": bool(user.is_verified),
        "city_id": user.city_id,
        "city_name": city_name,
    }


@router.patch("/me", response_model=ClientMeResponse)
async def update_me(
    data: ClientMeUpdate,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Update own name/city (progressive profiling, no verification resend)."""
    if data.name is not None:
        user.name = data.name
    if data.city_id is not None:
        city_exists = (await db.execute(
            select(City.id).where(City.id == data.city_id)
        )).scalar_one_or_none()
        if city_exists is None:
            raise HTTPException(status_code=404, detail="Город не найден")
        user.city_id = data.city_id
    await db.commit()
    await db.refresh(user)
    return await get_me(user, db)


@router.get("/stats", response_model=ClientStatsResponse)
async def get_my_stats(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Cabinet dashboard: spending, visits, favorites (completed only for money)."""
    profile = await _get_or_create_profile(db, user)
    rows = (await db.execute(
        select(Appointment, Service.price, Service.name,
               MasterProfile.id, User.name.label("master_name"),
               Service.id.label("service_id"))
        .join(Service, Appointment.service_id == Service.id)
        .join(MasterProfile, Appointment.master_id == MasterProfile.id)
        .join(User, MasterProfile.user_id == User.id)
        .where(Appointment.client_id == profile.id)
    )).all()

    total_spent = 0.0
    completed = upcoming = cancelled = 0
    master_visits: dict = {}
    service_visits: dict = {}
    for a, price, service_name, master_id, master_name, service_id in rows:
        if a.status == "completed":
            completed += 1
            total_spent += float(price or 0)
            master_visits[master_id] = master_visits.get(master_id, [master_name, 0])
            master_visits[master_id][1] += 1
            service_visits[service_id] = service_visits.get(
                service_id, [service_name, 0])
            service_visits[service_id][1] += 1
        elif a.status in ("pending", "confirmed"):
            if a.appointment_date and a.appointment_date.replace(tzinfo=None) >= utcnow_naive():
                upcoming += 1
        elif a.status == "cancelled":
            cancelled += 1

    def _fav(d):
        if not d:
            return None
        key = max(d, key=lambda k: d[k][1])
        return {"id": key, "name": d[key][0], "visits": d[key][1]}

    return {
        "total_spent": round(total_spent, 2),
        "completed_visits": completed,
        "upcoming_count": upcoming,
        "cancelled_count": cancelled,
        "favorite_master": _fav(master_visits),
        "favorite_service": _fav(service_visits),
    }


@router.get("/appointments", response_model=List[AppointmentWithDetails])
async def get_my_appointments(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """All own appointments, newest first (frontend splits upcoming/history)."""
    profile = await _get_or_create_profile(db, user)
    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client_profile).joinedload(ClientProfile.user),
            selectinload(Appointment.service),
            selectinload(Appointment.master_profile).joinedload(MasterProfile.user),
        )
        .where(Appointment.client_id == profile.id)
        .order_by(Appointment.appointment_date.desc())
    )
    appointments = result.scalars().all()
    logger.info("Client user_id=%s fetched %d appointments", user.id, len(appointments))
    return [_to_details(a) for a in appointments]


@router.post("/appointments/{appointment_id}/cancel",
             response_model=AppointmentWithDetails)
async def cancel_my_appointment(
    appointment_id: int,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Cancel own pending/confirmed appointment (404 for чужой, 400 for final)."""
    profile = await _get_or_create_profile(db, user)
    result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client_profile).joinedload(ClientProfile.user),
            selectinload(Appointment.service),
            selectinload(Appointment.master_profile).joinedload(MasterProfile.user),
        )
        .where(Appointment.id == appointment_id,
               Appointment.client_id == profile.id)
    )
    appointment = result.scalar_one_or_none()
    if appointment is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if appointment.status not in CANCELLABLE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Можно отменить только ожидающую или подтверждённую запись",
        )
    appointment.status = "cancelled"
    await log_action(
        db, user.id, "cancel", "appointment", appointment.id,
        f"Клиент отменил запись {appointment.id}", level="info",
    )
    await db.commit()
    logger.info("Client user_id=%s cancelled appointment %s", user.id, appointment.id)
    return _to_details(appointment)

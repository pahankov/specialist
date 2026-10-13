"""Client cabinet endpoints — own profile, own appointments, own cancel."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.dependencies.auth import require_client
from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.city import City
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.service import Service
from app.models.user import User
from app.models.working_hour import WorkingHour
from app.modules.client.schemas import (
    ClientMeResponse, ClientMeUpdate, ClientStatsResponse,
)
from app.modules.admin.notifications import (
    client_inbox, client_mark_read, client_read_all, client_unread_count,
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
    service = a.service
    return {
        "id": a.id,
        "master_id": a.master_id,
        "service_id": a.service_id,
        "bundle_id": a.bundle_id,
        "bundle_name": a.bundle_name,
        "client_id": a.client_id,
        "appointment_date": a.appointment_date,
        "status": a.status,
        "notes": a.notes,
        "client_name": a.client_profile.user.name if a.client_profile else None,
        "client_phone": a.client_profile.user.phone if a.client_profile else None,
        "service_name": a.bundle_name or (service.name if service else None),
        "service_price": (float(a.price) if a.price is not None
                          else (float(service.price) if service and service.price is not None else None)),
        "master_name": a.master_profile.user.name if a.master_profile else None,
    }


@router.get("/me", response_model=ClientMeResponse)
async def get_me(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Own profile (name/phone/city/address for the cabinet header)."""
    profile = await _get_or_create_profile(db, user)
    city_name = None
    if user.city_id:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == user.city_id)
        )).scalar_one_or_none()
    return {
        "id": user.id,
        "name": user.name,
        "last_name": user.last_name,
        "phone": user.phone,
        "email": user.email,
        "is_verified": bool(user.is_verified),
        "city_id": user.city_id,
        "city_name": city_name,
        "address": profile.address,
    }


@router.patch("/me", response_model=ClientMeResponse)
async def update_me(
    data: ClientMeUpdate,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Update own name/city/address (progressive profiling).

    Names recompose the display `name` ("Имя Фамилия") like master profile.
    """
    if data.name is not None:
        first = data.name.strip()
        last = (data.last_name.strip() if data.last_name is not None
                else (user.last_name or ""))
        user.name = f"{first} {last}".strip() if last else first
        user.last_name = last or None
    elif data.last_name is not None:
        last = data.last_name.strip()
        first = user.name.split(" ")[0] if user.name else ""
        user.name = f"{first} {last}".strip() if last else first
        user.last_name = last or None
    if data.city_id is not None:
        city_exists = (await db.execute(
            select(City.id).where(City.id == data.city_id)
        )).scalar_one_or_none()
        if city_exists is None:
            raise HTTPException(status_code=404, detail="Город не найден")
        user.city_id = data.city_id
    if data.address is not None:
        profile = await _get_or_create_profile(db, user)
        profile.address = data.address.strip() or None
    await db.commit()
    await db.refresh(user)
    return await get_me(user, db)


@router.delete("/me", status_code=200)
async def delete_me(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Delete own client account (soft delete + PII anonymization).

    Future appointments are cancelled, past history is kept for the
    3-year retention promised in /privacy.
    """
    from app.services.account_deletion import delete_own_account
    return await delete_own_account(db, user)


@router.get("/stats", response_model=ClientStatsResponse)
async def get_my_stats(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Cabinet dashboard: spending, visits, favorites (completed only for money)."""
    profile = await _get_or_create_profile(db, user)
    rows = (await db.execute(
        select(Appointment,
               func.coalesce(Appointment.price, Service.price),
               func.coalesce(Appointment.bundle_name, Service.name),
               MasterProfile.id, User.name.label("master_name"),
               Service.id.label("service_id"),
               Appointment.bundle_id, Appointment.bundle_name)
        .outerjoin(Service, Appointment.service_id == Service.id)
        .join(MasterProfile, Appointment.master_id == MasterProfile.id)
        .join(User, MasterProfile.user_id == User.id)
        .where(Appointment.client_id == profile.id)
    )).all()

    total_spent = 0.0
    completed = upcoming = cancelled = 0
    master_visits: dict = {}
    service_visits: dict = {}
    for a, price, item_name, master_id, master_name, service_id, bundle_id, bundle_name in rows:
        if a.status == "completed":
            completed += 1
            total_spent += float(price or 0)
            master_visits[master_id] = master_visits.get(master_id, [master_name, 0])
            master_visits[master_id][1] += 1
            # Bundles live in their own bucket (never mixed with services).
            # Negative id space avoids collisions with service ids.
            key = -int(bundle_id) if bundle_id is not None else service_id
            service_visits[key] = service_visits.get(key, [item_name, 0])
            service_visits[key][1] += 1
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


class ClientBookingCreate(BaseModel):
    master_id: int = Field(description="MasterProfile.id")
    service_id: Optional[int] = Field(default=None)
    bundle_id: Optional[int] = Field(default=None)
    appointment_date: datetime
    notes: Optional[str] = Field(default=None, max_length=500)


@router.get("/booking/schedule")
async def get_booking_schedule(
    master_id: int = Query(..., description="MasterProfile.id"),
    month: str = Query(..., description="YYYY-MM"),
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Active schedule of a master for the cabinet booking wizard.

    No personal data: working days + work window + busy granules
    (date/time/duration only) for the requested month.
    """
    try:
        year, mon = [int(x) for x in month.split("-")]
        assert 1 <= mon <= 12
    except (ValueError, AssertionError):
        raise HTTPException(status_code=400, detail="month: ГГГГ-ММ")

    mp = (await db.execute(
        select(MasterProfile).where(MasterProfile.id == master_id)
    )).scalar_one_or_none()
    if mp is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    mp_user = (await db.execute(
        select(User).where(User.id == mp.user_id)
    )).scalar_one_or_none()
    if mp_user is None or mp_user.is_active is False or mp.status != "active":
        raise HTTPException(status_code=404, detail="Мастер недоступен")

    from app.services.client_visibility import is_client_blocked
    _me_profile = await _get_or_create_profile(db, user)
    if await is_client_blocked(db, mp.id, _me_profile.id):
        raise HTTPException(
            status_code=403,
            detail="Этот мастер вас заблокировал. Выберите другого мастера.")

    month_prefix = f"{year:04d}-{mon:02d}"
    hours = (await db.execute(
        select(WorkingHour).where(
            WorkingHour.master_id == mp.id,
            WorkingHour.is_active == True,  # noqa: E712
        )
    )).scalars().all()
    working = [
        {"date": h.schedule_date.isoformat(),
         "start": h.start_time.strftime("%H:%M"),
         "end": h.end_time.strftime("%H:%M")}
        for h in hours
        if h.schedule_date.isoformat().startswith(month_prefix)
    ]

    appts = (await db.execute(
        select(Appointment,
               func.coalesce(Service.duration_minutes,
                             Appointment.duration_minutes))
        .outerjoin(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.master_id == mp.id,
            Appointment.status != "cancelled",
        )
    )).all()
    busy = [
        {"appointment_date": a.appointment_date.isoformat(),
         "status": a.status, "service_duration": dur}
        for a, dur in appts
        if a.appointment_date.isoformat().startswith(month_prefix)
    ]

    return {
        "master_id": mp.id,
        "window": {
            "start_hour": mp.work_start_hour if mp.work_start_hour is not None else 8,
            "end_hour": mp.work_end_hour if mp.work_end_hour is not None else 22,
        },
        "working_hours": working,
        "busy": busy,
    }


@router.post("/appointments", response_model=AppointmentWithDetails, status_code=201)
async def book_my_appointment(
    data: ClientBookingCreate,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Book an appointment for oneself (cabinet wizard)."""
    from datetime import timedelta

    profile = await _get_or_create_profile(db, user)

    mp = (await db.execute(
        select(MasterProfile).where(MasterProfile.id == data.master_id)
    )).scalar_one_or_none()
    if mp is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    mp_user = (await db.execute(
        select(User).where(User.id == mp.user_id)
    )).scalar_one_or_none()
    if mp_user is None or mp_user.is_active is False or mp.status != "active":
        raise HTTPException(status_code=404, detail="Мастер недоступен")

    from app.services.client_visibility import is_client_blocked
    if await is_client_blocked(db, mp.id, profile.id):
        raise HTTPException(
            status_code=403,
            detail="Этот мастер вас заблокировал. Выберите другого мастера.")

    appt_dt = data.appointment_date.replace(tzinfo=None)
    if appt_dt <= utcnow_naive():
        raise HTTPException(status_code=400, detail="Нельзя записаться в прошлое")
    from app.services.booking import find_conflict, format_slot, resolve_booking_item
    from app.services.notifications import notify_user
    # Exactly one of service_id / bundle_id; facts resolved server-side.
    item = await resolve_booking_item(db, mp.id, data.service_id, data.bundle_id)
    if await find_conflict(db, mp.id, appt_dt, item["duration_minutes"]):
        raise HTTPException(status_code=409, detail="Это время уже занято")

    appointment = Appointment(
        master_id=mp.id, service_id=item["service_id"], client_id=profile.id,
        bundle_id=item["bundle_id"], bundle_name=item["bundle_name"],
        duration_minutes=item["duration_minutes"], price=item["price"],
        appointment_date=appt_dt, status="pending",
        notes=(data.notes or "").strip() or None,
    )
    db.add(appointment)
    await db.flush()
    from app.services.client_visibility import unhide_client
    await unhide_client(db, mp.id, profile.id)
    client_note = (data.notes or "").strip()
    await notify_user(
        db, recipient_id=mp.user_id,
        text=f"Новая запись: {user.name} — {item['name']}, {format_slot(appt_dt)}"
             + (f" — «{client_note[:120]}»" if client_note else ""),
        sender_id=user.id, audience="booking", link="appointments",
    )
    await log_action(
        db, user.id, "create", "appointment", None,
        f"Клиент записался к мастеру {mp.id} на {appt_dt.isoformat()}", level="info",
    )
    await db.commit()
    await db.refresh(appointment)
    logger.info("Client user_id=%s booked appointment %s", user.id, appointment.id)

    full = (await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client_profile).joinedload(ClientProfile.user),
            selectinload(Appointment.service),
            selectinload(Appointment.master_profile).joinedload(MasterProfile.user),
        )
        .where(Appointment.id == appointment.id)
    )).scalar_one()
    return _to_details(full)


@router.get("/bundles")
async def get_bundles(
    master_id: int = Query(..., description="MasterProfile.id"),
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Active complexes of a master for the booking wizard (separate list)."""
    from app.models.service_bundle import ServiceBundle
    from app.modules.admin.bundles import _bundle_to_dict

    mp = (await db.execute(
        select(MasterProfile).where(MasterProfile.id == master_id)
    )).scalar_one_or_none()
    if mp is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    rows = (await db.execute(
        select(ServiceBundle).where(ServiceBundle.master_id == mp.id,
                                    ServiceBundle.is_active == True)  # noqa: E712
        .order_by(ServiceBundle.name)
    )).scalars().all()
    return [await _bundle_to_dict(db, b) for b in rows]


@router.get("/notifications/inbox")
async def get_notifications_inbox(
    unread_only: bool = False,
    page: int = 1,
    page_size: int = 20,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Own bell inbox (newest first + unread counter)."""
    return await client_inbox(db, user, unread_only, page, page_size)


@router.get("/notifications/unread-count")
async def get_notifications_unread(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    return await client_unread_count(db, user)


@router.post("/notifications/{notif_id}/read")
async def read_notification(
    notif_id: int,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    return await client_mark_read(db, user, notif_id)


@router.post("/notifications/read-all")
async def read_all_notifications(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    return await client_read_all(db, user)

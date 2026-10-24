"""Admin appointment creation: direct create + panel booking."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

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


async def _find_or_create_client(
    db: AsyncSession, phone: str, name: str, created_by: int | None = None,
    city_id: int | None = None,
) -> tuple[User, ClientProfile]:
    """Helper: find existing client by phone or create new one.

    Returns (user, profile). Appointment.client_id is a ClientProfile.id
    (same as the /book endpoint stores) — never a users.id.
    `city_id` (the booking master's city) is inherited by brand-new
    clients so they are matchable by city from the very first visit.
    """
    from app.schemas.client import normalize_phone
    normalized = normalize_phone(phone)
    result = await db.execute(select(User).where(User.phone == normalized))
    user = result.scalar_one_or_none()
    if not user:
        from app.services.names import name_fields
        full_name, last_name = name_fields(name)
        user = User(name=full_name, last_name=last_name, phone=normalized,
                    role=UserRole.CLIENT, created_by=created_by,
                    city_id=city_id)
        db.add(user)
        await db.flush()
        from app.services.clients import get_or_create_profile
        client_profile = await get_or_create_profile(db, user)
        # Flush-only: the caller owns the transaction and may still reject
        # the booking (conflict/invalid service) without creating a user.
        await db.refresh(user)
        await db.refresh(client_profile)
        return user, client_profile
    profile_result = await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )
    profile = profile_result.scalar_one_or_none()
    if profile is None:
        from app.services.clients import get_or_create_profile
        profile = await get_or_create_profile(db, user)
    return user, profile


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new appointment."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
        .with_for_update()
    )
    mp = result.scalar_one_or_none()
    if not mp or data.master_id != mp.id:
        raise HTTPException(status_code=403, detail="Not your master")

    from app.services.booking import find_conflict, resolve_booking_item
    appt_dt = data.appointment_date.replace(tzinfo=None)
    item = await resolve_booking_item(db, mp.id, data.service_id)
    if await find_conflict(db, mp.id, appt_dt, item["duration_minutes"]):
        raise HTTPException(status_code=409, detail="Это время уже занято")

    client, profile = await _find_or_create_client(
        db, data.client_phone, data.client_name, created_by=master.id,
        city_id=master.city_id)
    new_appointment = Appointment(
        master_id=data.master_id, service_id=item["service_id"],
        client_id=profile.id, duration_minutes=item["duration_minutes"],
        price=item["price"], discount_label=item.get("discount_label") or None,
        appointment_date=appt_dt, status="pending", notes=data.notes,
        created_by_role=("admin" if master.role == UserRole.ADMIN else "master"),
        created_by_user_id=master.id,
    )
    db.add(new_appointment)
    await db.flush()
    await db.refresh(new_appointment)
    from app.services.client_visibility import unhide_client
    await unhide_client(db, data.master_id, profile.id)
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
    if master.role == UserRole.ADMIN:
        # Superadmins have no profile of their own: book for the selected master
        if data.master_id is None:
            raise HTTPException(status_code=400, detail="Укажите мастера (master_id)")
        result = await db.execute(
            select(MasterProfile).where(MasterProfile.id == data.master_id)
            .with_for_update()
        )
        mp = result.scalar_one_or_none()
        if not mp:
            raise HTTPException(status_code=404, detail="Мастер не найден")
    else:
        result = await db.execute(
            select(MasterProfile).where(MasterProfile.user_id == master.id)
            .with_for_update()
        )
        mp = result.scalar_one_or_none()
        if not mp:
            raise HTTPException(status_code=403, detail="Not a master")

    client_result = await db.execute(
        select(User).options(joinedload(User.client_profile)).where(User.id == data.client_id)
    )
    user = client_result.scalar_one_or_none()
    # Dual-role: masters book as clients too; only ADMINs have no client side.
    if not user or user.role.value not in ("CLIENT", "MASTER"):
        raise HTTPException(status_code=404, detail="Клиент не найден")
    if user.client_profile is None:
        from app.services.clients import get_or_create_profile
        user.client_profile = await get_or_create_profile(db, user)
        await db.flush()

    from app.services.booking import find_conflict, resolve_booking_item
    # Exactly one of service_id / bundle_id; facts resolved server-side
    # (bundles carry snapshots, like the cabinet wizard).
    item = await resolve_booking_item(db, mp.id, data.service_id,
                                      data.bundle_id)
    if await find_conflict(db, mp.id, data.appointment_date.replace(tzinfo=None),
                           item["duration_minutes"]):
        raise HTTPException(status_code=409, detail="Это время уже занято")

    notes = "Запись из админ-панели"
    if data.notes:
        notes = f"{notes}. {data.notes}"

    new_appointment = Appointment(
        master_id=mp.id, service_id=item["service_id"],
        client_id=user.client_profile.id,
        bundle_id=item["bundle_id"], bundle_name=item["bundle_name"],
        duration_minutes=item["duration_minutes"], price=item["price"],
        discount_label=item.get("discount_label") or None,
        appointment_date=data.appointment_date, status=data.status, notes=notes,
        created_by_role=("admin" if master.role == UserRole.ADMIN else "master"),
        created_by_user_id=master.id,
    )
    db.add(new_appointment)
    from app.services.client_visibility import unhide_client
    await unhide_client(db, mp.id, user.client_profile.id)
    await db.commit()
    await db.refresh(new_appointment)
    return new_appointment

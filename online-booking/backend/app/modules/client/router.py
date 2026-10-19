"""Client cabinet endpoints — own profile, own appointments, own cancel."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload
from typing import List, Optional
from pydantic import BaseModel, Field

from app.database import get_db
from app.dependencies.auth import require_client
from app.middleware.rate_limit import limiter
from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.city import City
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.service import Service
from app.models.user import User
from app.models.user_contact import UserContact
from app.models.working_hour import WorkingHour
from app.modules.client.schemas import (
    ClientContactOut, ClientMeResponse, ClientMeUpdate, ClientStatsResponse,
)
from app.services.contacts import (
    ContactTaken,
    InvalidContact,
    attach_contact,
    get_contacts,
    remove_contact,
    set_primary,
)
from app.services.inbox import (
    client_inbox,
    client_mark_read,
    client_read_all,
    client_unread_count,
    delete_own_notifications,
)
from app.schemas.appointment import AppointmentWithDetails
from app.services.audit import log_action
from app.services.bundles import bundle_to_dict
from app.services.clients import get_or_create_profile
from app.services.coupons import coupon_discount, coupon_to_dict, describe_coupon, resolve_coupon
from app.services.names import set_names
from app.services.reviews import review_to_dict
from app.utils import localnow_naive

logger = get_logger(__name__)

router = APIRouter()

CANCELLABLE = ("pending", "confirmed")


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
                          else (service.effective_price if service else None)),
        "master_name": a.master_profile.user.name if a.master_profile else None,
    }


def _contact_out(c: UserContact) -> dict:
    """Serialize one contact for the cabinet (verify flags included)."""
    return {
        "id": c.id,
        "contact_type": c.contact_type,
        "value": c.value,
        "is_verified": bool(c.is_verified),
        "verified_via": c.verified_via,
        "is_primary": bool(c.is_primary),
    }


@router.get("/me", response_model=ClientMeResponse)
async def get_me(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Own profile (name/phone/city/address for the cabinet header)."""
    profile = await get_or_create_profile(db, user)
    city_name = None
    if user.city_id:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == user.city_id)
        )).scalar_one_or_none()
    contacts = await get_contacts(db, user.id)
    return {
        "id": user.id,
        "name": user.name,
        "last_name": user.last_name,
        "phone": user.phone,
        "email": user.email,
        "is_verified": bool(user.is_verified),
        "contacts": [_contact_out(c) for c in contacts],
        "has_password": user.hashed_password is not None,
        "max_bound": user.max_user_id is not None,
        "max_username": user.max_username,
        "vk_bound": user.vk_user_id is not None,
        "yandex_bound": user.yandex_user_id is not None,
        "avatar_url": user.avatar_url,
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
        last = (data.last_name.strip() if data.last_name is not None
                else (user.last_name or ""))
        set_names(user, data.name, last)
    elif data.last_name is not None:
        first = user.name.split(" ")[0] if user.name else ""
        set_names(user, first, data.last_name)
    if data.city_id is not None:
        city_exists = (await db.execute(
            select(City.id).where(City.id == data.city_id)
        )).scalar_one_or_none()
        if city_exists is None:
            raise HTTPException(status_code=404, detail="Город не найден")
        user.city_id = data.city_id
    if data.address is not None:
        profile = await get_or_create_profile(db, user)
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


# ─── Contacts (1.79.0 contact model) ──────────────────────────────────


class ClientContactCreate(BaseModel):
    contact_type: str = Field(pattern="^(phone|email)$")
    value: str = Field(min_length=1, max_length=255)


async def _own_contact_or_404(
    db: AsyncSession, user_id: int, contact_id: int
) -> UserContact:
    contact = (await db.execute(
        select(UserContact).where(
            UserContact.id == contact_id,
            UserContact.user_id == user_id,
        )
    )).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=404, detail="Контакт не найден")
    return contact


@router.post("/contacts", response_model=ClientContactOut, status_code=201)
@limiter.limit("10/minute")
async def add_my_contact(
    request: Request,
    data: ClientContactCreate,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Add a phone/email to own account (lands unverified by design).

    Verification levels come from social logins / emailed codes, never from
    self-typing. A value held by another account — as a contact row OR in
    the legacy column — is rejected: transfers happen only on
    provider-confirmed logins, not from a profile screen.
    """
    from app.services.contacts import find_user_by_contact

    holder = await find_user_by_contact(db, data.contact_type, data.value)
    if holder is not None and holder.id != user.id:
        raise HTTPException(
            status_code=409,
            detail="Этот контакт уже привязан к другому аккаунту",
        )
    try:
        contact, _ = await attach_contact(db, user, data.contact_type, data.value)
    except InvalidContact:
        raise HTTPException(
            status_code=422,
            detail=("Некорректный телефон" if data.contact_type == "phone"
                    else "Некорректный email"),
        )
    except ContactTaken:
        raise HTTPException(
            status_code=409,
            detail="Этот контакт уже привязан к другому аккаунту",
        )
    await log_action(db, user.id, "contact_add", "user_contact", contact.id,
                     f"Добавлен контакт {contact.contact_type}", level="info")
    await db.commit()
    return _contact_out(contact)


@router.delete("/contacts/{contact_id}", response_model=dict)
async def remove_my_contact(
    contact_id: int,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Detach an own contact (another of the type becomes primary).

    A password account must keep at least one contact — otherwise no
    identifier maps to it and password login becomes impossible.
    """
    contact = await _own_contact_or_404(db, user.id, contact_id)
    if user.hashed_password is not None:
        all_contacts = await get_contacts(db, user.id)
        if len(all_contacts) <= 1:
            raise HTTPException(
                status_code=400,
                detail="Это последний контакт аккаунта — иначе вход по "
                       "паролю станет невозможен. Сначала добавьте другой.",
            )
    removed_type = contact.contact_type
    await remove_contact(db, user, contact.contact_type, contact.value)
    await log_action(db, user.id, "contact_remove", "user_contact", contact_id,
                     f"Удалён контакт {removed_type}", level="info")
    await db.commit()
    return {"ok": True}


@router.post("/contacts/{contact_id}/primary", response_model=ClientContactOut)
async def make_my_contact_primary(
    contact_id: int,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Move a contact into the primary slot of its type."""
    contact = await _own_contact_or_404(db, user.id, contact_id)
    contact = await set_primary(db, user, contact.contact_type, contact.value)
    await db.commit()
    return _contact_out(contact)


@router.get("/stats", response_model=ClientStatsResponse)
async def get_my_stats(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Cabinet dashboard: spending, visits, favorites (completed only for money)."""
    profile = await get_or_create_profile(db, user)
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
            if a.appointment_date and a.appointment_date.replace(tzinfo=None) >= localnow_naive():
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
    profile = await get_or_create_profile(db, user)
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
    profile = await get_or_create_profile(db, user)
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
    notes: Optional[str] = Field(default=None, max_length=140)
    coupon_code: Optional[str] = Field(default=None, max_length=24)


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
    _me_profile = await get_or_create_profile(db, user)
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
@limiter.limit("30/minute")
async def book_my_appointment(
    request: Request,
    data: ClientBookingCreate,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Book an appointment for oneself (cabinet wizard)."""
    from datetime import timedelta

    profile = await get_or_create_profile(db, user)

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
    if mp.user_id == user.id:
        raise HTTPException(status_code=400,
                            detail="Нельзя записаться к самому себе")

    from app.services.client_visibility import is_client_blocked
    if await is_client_blocked(db, mp.id, profile.id):
        raise HTTPException(
            status_code=403,
            detail="Этот мастер вас заблокировал. Выберите другого мастера.")

    appt_dt = data.appointment_date.replace(tzinfo=None)
    if appt_dt <= localnow_naive():
        raise HTTPException(status_code=400, detail="Нельзя записаться в прошлое")
    from app.services.booking import find_conflict, format_slot, resolve_booking_item
    from app.services.notifications import notify_user
    # Exactly one of service_id / bundle_id; facts resolved server-side.
    item = await resolve_booking_item(db, mp.id, data.service_id, data.bundle_id)
    if await find_conflict(db, mp.id, appt_dt, item["duration_minutes"]):
        raise HTTPException(status_code=409, detail="Это время уже занято")

    coupon = None
    coupon_off = 0.0
    if (data.coupon_code or "").strip():
        coupon = await resolve_coupon(db, mp.id, data.coupon_code, user)
        coupon_off = coupon_discount(item["price"], coupon)

    label_parts = [item.get("discount_label") or ""]
    if coupon is not None:
        label_parts.append(f"купон {coupon.code} −{coupon_off:g} ₽")
    discount_label = " + ".join(p for p in label_parts if p) or None

    appointment = Appointment(
        master_id=mp.id, service_id=item["service_id"], client_id=profile.id,
        bundle_id=item["bundle_id"], bundle_name=item["bundle_name"],
        duration_minutes=item["duration_minutes"],
        price=round(float(item["price"]) - coupon_off, 2),
        discount_label=discount_label,
        appointment_date=appt_dt,
        status="confirmed" if mp.auto_confirm else "pending",
        notes=(data.notes or "").strip() or None,
    )
    db.add(appointment)
    await db.flush()
    if coupon is not None:
        from app.models.coupon import CouponUse
        db.add(CouponUse(coupon_id=coupon.id, appointment_id=appointment.id,
                         user_id=user.id, amount=coupon_off))
        coupon.used_count = (coupon.used_count or 0) + 1
    from app.services.client_visibility import unhide_client
    await unhide_client(db, mp.id, profile.id)
    client_note = (data.notes or "").strip()
    await notify_user(
        db, recipient_id=mp.user_id,
        text=f"Новая запись: {user.name} — {item['name']}, {format_slot(appt_dt)}"
             + (f" — «{client_note[:120]}»" if client_note else ""),
        sender_id=user.id, audience="booking",
        link=f"appointments:{appointment.id}",
    )
    await log_action(
        db, user.id, "create", "appointment", None,
        f"Клиент записался к мастеру {mp.id} на {appt_dt.isoformat()}"
        + (f" купон={coupon.code} −{coupon_off}" if coupon is not None else ""),
        level="info",
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


class CouponPreview(BaseModel):
    master_id: int
    service_id: Optional[int] = Field(default=None)
    bundle_id: Optional[int] = Field(default=None)
    code: str = Field(min_length=1, max_length=24)


@router.get("/coupons/mine")
async def my_coupons(
    master_id: Optional[int] = Query(default=None),
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Coupons issued to me (optionally of one master): code + terms.

    Personal (user_ids) plus broadcast ones from masters I visit.
    Spent/expired/inactive are excluded — the list is always usable.
    """
    from app.models.coupon import Coupon

    profile = await get_or_create_profile(db, user)
    my_master_ids = set((await db.execute(
        select(Appointment.master_id).where(Appointment.client_id == profile.id)
    )).scalars().all())
    q = select(Coupon).where(Coupon.is_active == True)  # noqa: E712
    if master_id is not None:
        q = q.where(Coupon.master_id == master_id)
    rows = (await db.execute(q.order_by(Coupon.id.desc()))).scalars().all()
    now = localnow_naive()
    out = []
    for c in rows:
        if c.valid_until is not None and now >= c.valid_until.replace(tzinfo=None):
            continue
        if c.max_uses and (c.used_count or 0) >= c.max_uses:
            continue
        if c.user_ids:
            if user.id not in c.user_ids:
                continue
        elif c.master_id not in my_master_ids:
            continue
        d = coupon_to_dict(c)
        d["terms"] = describe_coupon(c)
        out.append(d)
    return out


@router.post("/coupons/preview")
@limiter.limit("10/minute")
async def preview_coupon(
    request: Request,
    data: CouponPreview,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Check a promo code before booking: new total or a friendly error."""
    from app.services.booking import resolve_booking_item

    mp = (await db.execute(
        select(MasterProfile).where(MasterProfile.id == data.master_id)
    )).scalar_one_or_none()
    if mp is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    item = await resolve_booking_item(db, mp.id, data.service_id, data.bundle_id)
    coupon = await resolve_coupon(db, mp.id, data.code, user)
    off = coupon_discount(item["price"], coupon)
    return {
        "ok": True,
        "code": coupon.code,
        "terms": describe_coupon(coupon),
        "base_price": round(float(item["price"]), 2),
        "discount": off,
        "new_price": round(float(item["price"]) - off, 2),
    }


@router.get("/bundles")
async def get_bundles(
    master_id: int = Query(..., description="MasterProfile.id"),
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Active complexes of a master for the booking wizard (separate list)."""
    from app.models.service_bundle import ServiceBundle

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
    return [await bundle_to_dict(db, b) for b in rows]


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


@router.delete("/notifications")
async def clear_notifications(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Delete all own bells (history cleanup)."""
    return await delete_own_notifications(db, user)


class ClientReviewCreate(BaseModel):
    appointment_id: int
    rating: float = Field(ge=1.0, le=5.0)
    comment: Optional[str] = Field(default=None, max_length=1000)


@router.get("/reviews/mine")
async def my_reviews(
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Own reviews (to mark rated appointments in history)."""
    from app.models.review import Review
    profile = await get_or_create_profile(db, user)
    rows = (await db.execute(
        select(Review).join(Appointment, Review.appointment_id == Appointment.id)
        .where(Appointment.client_id == profile.id)
        .order_by(Review.created_at.desc())
    )).scalars().all()
    return [review_to_dict(r) for r in rows]


@router.post("/reviews", status_code=201)
async def create_own_review(
    data: ClientReviewCreate,
    user: User = Depends(require_client),
    db: AsyncSession = Depends(get_db),
):
    """Rate an own visit: completed, or past its end even if not confirmed.

    Masters that never press "complete" must not block client feedback;
    the rating still counts once the visit time has passed.
    """
    from datetime import timedelta
    from app.models.review import Review
    profile = await get_or_create_profile(db, user)
    appt = (await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client_profile).joinedload(ClientProfile.user))
        .where(Appointment.id == data.appointment_id)
    )).scalar_one_or_none()
    if appt is None:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    # Legacy rows may store the user id instead of the profile id.
    if appt.client_id != profile.id and appt.client_id != user.id:
        raise HTTPException(status_code=403, detail="Чужая запись")
    if appt.status == "cancelled":
        raise HTTPException(status_code=400,
                            detail="Отменённую запись оценить нельзя")
    if appt.status != "completed":
        dur = appt.duration_minutes or 60
        try:
            end = appt.appointment_date.replace(tzinfo=None) + timedelta(minutes=int(dur))
        except Exception:
            end = None
        if end is None or end > localnow_naive():
            raise HTTPException(status_code=400,
                                detail="Оценить можно после визита")
    existing = (await db.execute(
        select(Review).where(Review.appointment_id == appt.id)
    )).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Отзыв уже оставлен")
    review = Review(
        appointment_id=appt.id, master_id=appt.master_id,
        client_name=user.name or "Клиент", client_phone=user.phone or "",
        rating=data.rating, comment=(data.comment or "").strip() or None,
        is_published=True,
    )
    db.add(review)
    await log_action(db, user.id, "create", "review", None,
                     f"Оценка {data.rating} мастеру {appt.master_id}", level="info")
    # Master gets a bell (jumps to profile reviews) — feedback is two-way.
    try:
        from app.services.notifications import notify_user
        mp_user_id = (await db.execute(
            select(MasterProfile.user_id).where(MasterProfile.id == appt.master_id)
        )).scalar_one_or_none()
        if mp_user_id is not None:
            await notify_user(
                db, recipient_id=mp_user_id,
                text=(f"⭐ Новая оценка {data.rating} от {user.name or 'клиента'}"
                      + (f" — «{(data.comment or '').strip()[:120]}»"
                         if (data.comment or "").strip() else "")),
                sender_id=user.id, audience="review", link="reviews",
            )
    except Exception as e:
        logger.warning("Review bell failed (non-fatal): %s", e)
    await db.commit()
    await db.refresh(review)
    return review_to_dict(review)

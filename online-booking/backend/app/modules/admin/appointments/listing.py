"""Admin appointment listing: paginated list + by-date range."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased, selectinload
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.user import User, UserRole
from app.models.service import Service
from app.models.master_profile import MasterProfile
from app.schemas.appointment import AppointmentWithDetails
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_master
from app.modules.admin.helpers import get_master_profile_id
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Aliases for the same table joined multiple times
_ClientUser = aliased(User, name="client_user")
_MasterUser = aliased(User, name="master_user")


@router.get("/appointments", response_model=PaginatedResponse[AppointmentWithDetails])
async def get_admin_appointments(
    master: User = Depends(require_master),
    status: Optional[str] = Query(None, description="Filter by status"),
    master_id: Optional[int] = Query(None, description="Filter by master ID (superadmin only)"),
    client_id: Optional[int] = Query(None, description="Filter by client ID"),
    service_id: Optional[int] = Query(None, description="Filter by service ID"),
    date_from: Optional[str] = Query(None, description="Filter by date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments with client and service details (paginated with total count)."""
    logger.info("Get appointments: master=%s, status=%s, master_id=%s, client_id=%s, service_id=%s, date_from=%s, date_to=%s, page=%d",
                master.id, status, master_id, client_id, service_id, date_from, date_to, page)
    offset = (page - 1) * page_size
    is_admin = master.role == UserRole.ADMIN

    # Parse date filters
    dt_from = None
    dt_to = None
    if date_from:
        from datetime import datetime as dt_datetime
        dt_from = dt_datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=None)
    if date_to:
        from datetime import datetime as dt_datetime
        dt_to = dt_datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=None)

    if is_admin:
        query = (
            select(Appointment, _ClientUser.name.label('client_name'), _ClientUser.phone.label('client_phone'),
                   Service.name.label('service_name'), Service.price.label('service_price'),
                   _MasterUser.name.label('master_name'))
            .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
            .join(_ClientUser, ClientProfile.user_id == _ClientUser.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .join(MasterProfile, Appointment.master_id == MasterProfile.id, isouter=True)
            .join(_MasterUser, MasterProfile.user_id == _MasterUser.id, isouter=True)
        )
        count_query = (
            select(func.count(Appointment.id))
            .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .join(MasterProfile, Appointment.master_id == MasterProfile.id, isouter=True)
        )
    else:
        # Regular master — get their master_profile first
        result = await db.execute(
            select(MasterProfile).where(MasterProfile.user_id == master.id)
        )
        mp = result.scalar_one_or_none()
        if not mp:
            return PaginatedResponse(items=[], total=0, page=page, page_size=page_size, total_pages=0)

        query = (
            select(Appointment, User.name.label('client_name'), User.phone.label('client_phone'),
                   Service.name.label('service_name'), Service.price.label('service_price'))
            .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
            .join(User, ClientProfile.user_id == User.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .where(Appointment.master_id == mp.id)
        )
        count_query = (
            select(func.count(Appointment.id))
            .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .where(Appointment.master_id == mp.id)
        )

    # Apply status filter
    if status:
        query = query.where(Appointment.status == status)
        count_query = count_query.where(Appointment.status == status)

    # Apply master_id filter (superadmin only)
    if master_id is not None:
        query = query.where(Appointment.master_id == master_id)
        count_query = count_query.where(Appointment.master_id == master_id)

    # Apply client_id filter. Accepts BOTH id spaces: ClientProfile.id
    # (used by appointments) and User.id (used by clients list responses),
    # resolving the latter to its profile.
    if client_id is not None:
        profile_ids = select(ClientProfile.id).where(
            (ClientProfile.id == client_id) | (ClientProfile.user_id == client_id)
        )
        query = query.where(Appointment.client_id.in_(profile_ids))
        count_query = count_query.where(Appointment.client_id.in_(profile_ids))

    # Apply service_id filter
    if service_id is not None:
        query = query.where(Appointment.service_id == service_id)
        count_query = count_query.where(Appointment.service_id == service_id)

    # Apply date range filters
    if dt_from is not None:
        query = query.where(Appointment.appointment_date >= dt_from)
        count_query = count_query.where(Appointment.appointment_date >= dt_from)
    if dt_to is not None:
        query = query.where(Appointment.appointment_date <= dt_to)
        count_query = count_query.where(Appointment.appointment_date <= dt_to)

    # Get total count
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get data (id tiebreak keeps pages deterministic on equal timestamps)
    query = query.order_by(Appointment.appointment_date.desc(), Appointment.id.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    # Clients hidden by this master keep their history rows, but render
    # anonymized instead of the real name/phone.
    hidden_cp_ids: set = set()
    if not is_admin:
        from app.models.master_hidden_client import (
            DELETED_CLIENT_NAME, MasterHiddenClient,
        )
        mp_id = await get_master_profile_id(db, master)
        hidden_rows = await db.execute(
            select(MasterHiddenClient.client_profile_id).where(
                MasterHiddenClient.master_profile_id == mp_id)
        )
        hidden_cp_ids = {r[0] for r in hidden_rows.all()}
    else:
        from app.models.master_hidden_client import DELETED_CLIENT_NAME

    items = []
    # Coupon codes per appointment (one query for the page).
    coupon_map: dict = {}
    page_ids = [row[0].id for row in rows]
    if page_ids:
        from app.models.coupon import Coupon, CouponUse
        cu = (await db.execute(
            select(CouponUse.appointment_id, Coupon.code)
            .join(Coupon, CouponUse.coupon_id == Coupon.id)
            .where(CouponUse.appointment_id.in_(page_ids))
        )).all()
        coupon_map = {aid: code for aid, code in cu}
    for row in rows:
        appt = row[0]
        client_name, client_phone = row[1], row[2]
        if appt.client_id in hidden_cp_ids:
            client_name, client_phone = DELETED_CLIENT_NAME, None
        items.append(AppointmentWithDetails(
            id=appt.id, master_id=appt.master_id, service_id=appt.service_id,
            bundle_id=appt.bundle_id, bundle_name=appt.bundle_name,
            client_id=appt.client_id, appointment_date=appt.appointment_date,
            status=appt.status, notes=appt.notes,
            client_name=client_name, client_phone=client_phone,
            # Bundle bookings: snapshots win over the (absent) service join.
            service_name=(appt.bundle_name or row[3]),
            service_price=(float(appt.price) if appt.price is not None
                           else (float(row[4]) if row[4] is not None else None)),
            # Admin branch selects master_name as 6th column; master branch has none
            master_name=row[5] if is_admin and len(row) > 5 else None,
            coupon_code=coupon_map.get(appt.id),
            discount_label=appt.discount_label,
        ))

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )


@router.get("/appointments/by-date")
async def get_appointments_by_date(
    date_from: str = Query(...),
    date_to: str = Query(...),
    master_id: Optional[int] = Query(None, description="Filter by master ID (superadmin only)"),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments for a date range."""
    start_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=None)
    end_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=None)

    is_admin = master.role == UserRole.ADMIN

    if is_admin and master_id is not None:
        query = (
            select(Appointment)
            .options(selectinload(Appointment.client_profile).joinedload(ClientProfile.user))
            .options(selectinload(Appointment.service))
            .where(Appointment.master_id == master_id,
                   Appointment.appointment_date >= start_dt, Appointment.appointment_date <= end_dt)
            .order_by(Appointment.appointment_date)
        )
    else:
        mp_id = await get_master_profile_id(db, master)
        query = (
            select(Appointment)
            .options(selectinload(Appointment.client_profile).joinedload(ClientProfile.user))
            .options(selectinload(Appointment.service))
            .where(Appointment.master_id == mp_id,
                   Appointment.appointment_date >= start_dt, Appointment.appointment_date <= end_dt)
            .order_by(Appointment.appointment_date)
        )

    result = await db.execute(query)
    appointments = result.scalars().all()
    hidden_cp_ids: set = set()
    if not is_admin:
        from app.models.master_hidden_client import (
            DELETED_CLIENT_NAME, MasterHiddenClient,
        )
        mp_id = await get_master_profile_id(db, master)
        hidden_rows = await db.execute(
            select(MasterHiddenClient.client_profile_id).where(
                MasterHiddenClient.master_profile_id == mp_id)
        )
        hidden_cp_ids = {r[0] for r in hidden_rows.all()}
    else:
        from app.models.master_hidden_client import DELETED_CLIENT_NAME
    return [
        {"id": a.id,
         "client_name": (DELETED_CLIENT_NAME
                         if a.client_id in hidden_cp_ids
                         else (a.client_profile.user.name if a.client_profile else "Unknown")),
         "client_phone": (None
                          if a.client_id in hidden_cp_ids
                          else (a.client_profile.user.phone if a.client_profile else "")),
         "service_id": a.service_id,
         "bundle_id": a.bundle_id,
         "service_name": a.bundle_name or (a.service.name if a.service else ""),
         "service_duration": (a.duration_minutes if a.duration_minutes is not None
                              else (a.service.duration_minutes if a.service else None)),
         "appointment_date": a.appointment_date.isoformat(), "status": a.status,
         "discount_label": a.discount_label,
         "notes": a.notes}
        for a in appointments
    ]

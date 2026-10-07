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

    # Apply client_id filter
    if client_id is not None:
        query = query.where(Appointment.client_id == client_id)
        count_query = count_query.where(Appointment.client_id == client_id)

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

    # Get data
    query = query.order_by(Appointment.appointment_date.desc()).offset(offset).limit(page_size)
    result = await db.execute(query)
    rows = result.all()

    items = []
    for row in rows:
        appt = row[0]
        items.append(AppointmentWithDetails(
            id=appt.id, master_id=appt.master_id, service_id=appt.service_id,
            client_id=appt.client_id, appointment_date=appt.appointment_date,
            status=appt.status, notes=appt.notes,
            client_name=row[1], client_phone=row[2], service_name=row[3], service_price=row[4]
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
    return [
        {"id": a.id, "client_name": a.client_profile.user.name if a.client_profile else "Unknown",
         "client_phone": a.client_profile.user.phone if a.client_profile else "",
         "service_name": a.service.name if a.service else "",
                     "appointment_date": a.appointment_date.isoformat(), "status": a.status}
         for a in appointments
    ]

"""Admin appointment CRUD endpoints with pagination."""
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import aliased, selectinload
from typing import List, Optional
from datetime import datetime, timedelta

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.user import User, UserRole
from app.models.service import Service
from app.models.master_profile import MasterProfile
from app.schemas.appointment import AppointmentWithDetails, AdminBookingCreate, AppointmentResponse, AppointmentCreate
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_master
from app.dependencies.crud import get_owned_or_404
from app.services.audit import log_action

router = APIRouter()

# Aliases for the same table joined multiple times
_ClientUser = aliased(User, name="client_user")
_MasterUser = aliased(User, name="master_user")


async def _find_or_create_client(db: AsyncSession, phone: str, name: str) -> User:
    """Helper: find existing client by phone or create new one."""
    from app.schemas.client import normalize_phone
    normalized = normalize_phone(phone)
    result = await db.execute(select(User).where(User.phone == normalized))
    user = result.scalar_one_or_none()
    if not user:
        user = User(name=name, phone=normalized, role="CLIENT")
        db.add(user)
        client_profile = ClientProfile(user_id=user.id)
        db.add(client_profile)
        await db.commit()
        await db.refresh(user)
    return user


# ─── Specific routes MUST come before generic /appointments ───

@router.patch("/appointments/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Confirm an appointment."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=403, detail="Not a master")
    
    appointment = await get_owned_or_404(db, Appointment, appointment_id, mp.id)
    appointment.status = "confirmed"
    await log_action(db, master.id, "confirm", "appointment", appointment.id, "Статус изменён на confirmed", level="info")
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.patch("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    reason: Optional[str] = Query(None),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an appointment."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=403, detail="Not a master")
    
    appointment = await get_owned_or_404(db, Appointment, appointment_id, mp.id)
    appointment.status = "cancelled"
    if reason:
        appointment.notes = f"{appointment.notes}\nОтмена: {reason}" if appointment.notes else f"Отмена: {reason}"
    await log_action(db, master.id, "cancel", "appointment", appointment.id, f"Причина: {reason}", level="warning")
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.patch("/appointments/{appointment_id}/complete")
async def complete_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Mark an appointment as completed."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=403, detail="Not a master")
    
    appointment = await get_owned_or_404(db, Appointment, appointment_id, mp.id)
    appointment.status = "completed"
    await log_action(db, master.id, "complete", "appointment", appointment.id, level="info")
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.delete("/appointments/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete an appointment."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=403, detail="Not a master")
    
    appointment = await get_owned_or_404(db, Appointment, appointment_id, mp.id)
    await log_action(db, master.id, "delete", "appointment", appointment_id, level="warning")
    await db.delete(appointment)
    await db.commit()
    return None


@router.patch("/appointments/{appointment_id}/no-show")
async def mark_no_show(
    appointment_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Mark an appointment as no-show. Increments client's no_show_count."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == master.id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=403, detail="Not a master")
    
    appointment = await get_owned_or_404(db, Appointment, appointment_id, mp.id)
    appointment.status = "cancelled"
    appointment.notes = f"{appointment.notes}\n\nНеявка" if appointment.notes else "Неявка"
    await log_action(db, master.id, "no-show", "appointment", appointment_id, level="warning")

    if appointment.client_id:
        client_result = await db.execute(
            select(ClientProfile).where(ClientProfile.id == appointment.client_id)
        )
        client = client_result.scalar_one_or_none()
        if client:
            client.no_show_count = (client.no_show_count or 0) + 1

    await db.commit()
    await db.refresh(appointment)
    return appointment


# ─── Generic routes ───

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

    client_result = await db.execute(select(User).where(User.id == data.client_id))
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
        query = (
            select(Appointment)
            .options(selectinload(Appointment.client_profile).joinedload(ClientProfile.user))
            .options(selectinload(Appointment.service))
            .where(Appointment.master_id == master.master_profile.id,
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

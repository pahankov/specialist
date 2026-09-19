"""Admin API endpoints for master dashboard."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta, time
import csv
import io
from app.database import get_db
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.models.master import Master
from app.models.working_hour import WorkingHour
from app.models.blocked_slot import BlockedSlot
from app.schemas.appointment import AppointmentResponse, AppointmentCreate, AppointmentWithDetails, AdminBookingCreate
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.schemas.working_hour import WorkingHourCreate, WorkingHourUpdate, WorkingHourResponse
from app.schemas.audit_log import AuditLogResponse, AuditLogListResponse
from app.schemas.blocked_slot import BlockedSlotCreate, BlockedSlotResponse
from app.api.dependencies import require_master
from app.api.admin_helpers import get_owned_or_404, get_or_404
from app.api.audit_helper import log_action

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
async def get_dashboard(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics for the authenticated master."""
    # Count appointments by status
    result = await db.execute(
        select(
            Appointment.status,
            func.count(Appointment.id)
        ).where(Appointment.master_id == master.id)
        .group_by(Appointment.status)
    )
    status_counts = {row[0]: row[1] for row in result.all()}

    # Total appointments
    total_result = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.master_id == master.id)
    )
    total_appointments = total_result.scalar() or 0

    # Total clients
    client_result = await db.execute(
        select(func.count(Client.id)).where(
            Client.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == master.id)
            )
        )
    )
    total_clients = client_result.scalar() or 0

    # Total services
    service_result = await db.execute(
        select(func.count(Service.id)).where(Service.master_id == master.id)
    )
    total_services = service_result.scalar() or 0

    # Recent appointments (last 10)
    recent_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client), selectinload(Appointment.service))
        .where(Appointment.master_id == master.id)
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()

    # Upcoming appointments (next 7 days)
    week_from_now = datetime.now() + timedelta(days=7)
    upcoming_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client), selectinload(Appointment.service))
        .where(
            Appointment.master_id == master.id,
            Appointment.appointment_date >= datetime.now(),
            Appointment.appointment_date <= week_from_now,
            Appointment.status != "cancelled"
        )
        .order_by(Appointment.appointment_date.asc())
    )
    upcoming_appointments = upcoming_result.scalars().all()

    # Revenue (confirmed appointments)
    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.master_id == master.id,
            Appointment.status == "confirmed"
        )
    )
    total_revenue = revenue_result.scalar() or 0

    return {
        "total_appointments": total_appointments,
        "status_counts": status_counts,
        "total_clients": total_clients,
        "total_services": total_services,
        "total_revenue": float(total_revenue),
        "recent_appointments": [
            {
                "id": a.id,
                "client_id": a.client_id,
                "client_name": a.client.name if a.client else None,
                "client_phone": a.client.phone if a.client else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status,
                "service_id": a.service_id,
                "service_name": a.service.name if a.service else None,
                "service_price": float(a.service.price) if a.service else 0
            }
            for a in recent_appointments
        ],
        "upcoming_appointments": [
            {
                "id": a.id,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status
            }
            for a in upcoming_appointments
        ]
    }


@router.get("/appointments", response_model=List[AppointmentWithDetails])
async def get_admin_appointments(
    master: Master = Depends(require_master),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments with client and service details for the authenticated master."""
    query = (
        select(
            Appointment,
            Client.name.label('client_name'),
            Client.phone.label('client_phone'),
            Service.name.label('service_name'),
            Service.price.label('service_price')
        )
        .join(Client, Appointment.client_id == Client.id, isouter=True)
        .join(Service, Appointment.service_id == Service.id, isouter=True)
        .where(Appointment.master_id == master.id)
    )

    if status:
        query = query.where(Appointment.status == status)

    query = query.order_by(Appointment.appointment_date.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    return [
        AppointmentWithDetails(
            id=row[0].id,
            master_id=row[0].master_id,
            service_id=row[0].service_id,
            client_id=row[0].client_id,
            appointment_date=row[0].appointment_date,
            status=row[0].status,
            notes=row[0].notes,
            client_name=row[1],
            client_phone=row[2],
            service_name=row[3],
            service_price=row[4]
        )
        for row in rows
    ]


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new appointment for the authenticated master."""
    from app.models.client import Client
    
    if data.master_id != master.id:
        raise HTTPException(status_code=403, detail="Not your master")
    
    # Find or create client
    result = await db.execute(
        select(Client).where(Client.phone == data.client_phone)
    )
    client = result.scalar_one_or_none()
    if not client:
        client = Client(name=data.client_name, phone=data.client_phone)
        db.add(client)
        await db.commit()
        await db.refresh(client)
    
    new_appointment = Appointment(
        master_id=data.master_id,
        service_id=data.service_id,
        client_id=client.id,
        appointment_date=data.appointment_date,
        status="pending",
        notes=data.notes
    )
    
    db.add(new_appointment)
    await db.commit()
    await db.refresh(new_appointment)
    return new_appointment


@router.patch("/appointments/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Confirm an appointment."""
    appointment = await get_owned_or_404(db, Appointment, appointment_id, master.id)
    appointment.status = "confirmed"
    await db.commit()
    await db.refresh(appointment)
    await log_action(db, master.id, "confirm", "appointment", appointment.id, "Статус изменён на confirmed")
    return appointment


@router.patch("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    reason: Optional[str] = Query(None),
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an appointment."""
    appointment = await get_owned_or_404(db, Appointment, appointment_id, master.id)
    appointment.status = "cancelled"
    if reason:
        appointment.notes = f"{appointment.notes}\nОтмена: {reason}" if appointment.notes else f"Отмена: {reason}"
    await db.commit()
    await db.refresh(appointment)
    await log_action(db, master.id, "cancel", "appointment", appointment.id, f"Причина: {reason}")
    return appointment


@router.patch("/appointments/{appointment_id}/complete")
async def complete_appointment(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Mark an appointment as completed."""
    appointment = await get_owned_or_404(db, Appointment, appointment_id, master.id)
    appointment.status = "completed"
    await db.commit()
    await db.refresh(appointment)
    await log_action(db, master.id, "complete", "appointment", appointment.id)
    return appointment


@router.delete("/appointments/{appointment_id}", status_code=200)
async def delete_appointment(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete an appointment."""
    appointment = await get_owned_or_404(db, Appointment, appointment_id, master.id)
    await log_action(db, master.id, "delete", "appointment", appointment_id)
    await db.delete(appointment)
    await db.commit()
    return {"detail": "Appointment deleted"}


@router.post("/appointments/book", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    data: AdminBookingCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Book an appointment from admin panel (select client from DB)."""
    from app.models.client import Client

    # Check service belongs to master
    service_result = await db.execute(
        select(Service).where(Service.id == data.service_id, Service.master_id == master.id)
    )
    service = service_result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    # Check client exists
    client_result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    # Check no conflict — overlapping time for the same master, not cancelled
    service_end = data.appointment_date + timedelta(minutes=service.duration_minutes)
    conflict_result = await db.execute(
        select(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.master_id == master.id,
            Appointment.status != "cancelled",
            Appointment.appointment_date < service_end,
            Appointment.appointment_date + timedelta(minutes=service.duration_minutes) > data.appointment_date
        )
        .limit(1)
    )
    if conflict_result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Это время уже занято")

    notes = "Запись из админ-панели"
    if data.notes:
        notes = f"{notes}. {data.notes}"

    new_appointment = Appointment(
        master_id=master.id,
        service_id=data.service_id,
        client_id=data.client_id,
        appointment_date=data.appointment_date,
        status=data.status,
        notes=notes
    )

    db.add(new_appointment)
    await db.commit()
    await db.refresh(new_appointment)
    return new_appointment


@router.get("/appointments/by-date")
async def get_appointments_by_date(
    date_from: str = Query(..., description="Start date YYYY-MM-DD"),
    date_to: str = Query(..., description="End date YYYY-MM-DD"),
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments for a date range."""
    from datetime import datetime
    from sqlalchemy.orm import selectinload
    
    start_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=None)
    end_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=None)
    
    query = (
        select(Appointment)
        .options(selectinload(Appointment.client), selectinload(Appointment.service))
        .where(
            Appointment.master_id == master.id,
            Appointment.appointment_date >= start_dt,
            Appointment.appointment_date <= end_dt
        )
        .order_by(Appointment.appointment_date)
    )
    result = await db.execute(query)
    appointments = result.scalars().all()
    
    return [
        {
            "id": a.id,
            "client_name": a.client.name if a.client else "Unknown",
            "client_phone": a.client.phone if a.client else "",
            "service_name": a.service.name if a.service else "",
            "appointment_date": a.appointment_date.isoformat(),
            "status": a.status
        }
        for a in appointments
    ]


@router.get("/working-hours", response_model=List[WorkingHourResponse])
async def get_working_hours(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get working hours for the authenticated master."""
    result = await db.execute(
        select(WorkingHour).where(WorkingHour.master_id == master.id)
        .order_by(WorkingHour.schedule_date)
    )
    hours = result.scalars().all()
    return hours


@router.post("/working-hours", response_model=WorkingHourResponse, status_code=201)
async def create_working_hour(
    data: WorkingHourCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create working hours for the authenticated master."""
    print(f'[WORKING-HOURS CREATE] schedule_date={data.schedule_date}, start={data.start_time}, end={data.end_time}')
    hour = WorkingHour(
        master_id=master.id,
        schedule_date=data.schedule_date,
        start_time=time.fromisoformat(data.start_time),
        end_time=time.fromisoformat(data.end_time)
    )
    db.add(hour)
    await db.flush()
    await db.refresh(hour)
    await db.commit()
    print(f'[WORKING-HOURS CREATE] Created id={hour.id}, schedule_date={hour.schedule_date}')
    return hour


@router.delete("/working-hours/{hour_id}", status_code=200)
async def delete_working_hour(
    hour_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete working hours for the authenticated master."""
    hour = await get_owned_or_404(db, WorkingHour, hour_id, master.id)
    await db.delete(hour)
    await db.commit()
    return {"detail": "Working hour deleted"}


@router.patch("/working-hours/{hour_id}", response_model=WorkingHourResponse, status_code=200)
async def update_working_hour(
    hour_id: int,
    data: WorkingHourUpdate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update working hours for the authenticated master."""
    hour = await get_owned_or_404(db, WorkingHour, hour_id, master.id)

    if data.schedule_date is not None:
        hour.schedule_date = data.schedule_date
    if data.start_time is not None:
        hour.start_time = time.fromisoformat(data.start_time)
    if data.end_time is not None:
        hour.end_time = time.fromisoformat(data.end_time)

    await db.commit()
    await db.refresh(hour)
    return hour


# ─── Services CRUD (admin only) ──────────────────────────────────────────────

@router.post("/services", response_model=ServiceResponse, status_code=201)
async def create_admin_service(
    data: ServiceCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a service for the authenticated master."""
    new_service = Service(
        master_id=master.id,
        name=data.name,
        description=data.description,
        duration_minutes=data.duration_minutes,
        price=data.price,
        is_active=True
    )
    db.add(new_service)
    await db.commit()
    await db.refresh(new_service)
    return new_service


@router.get("/services", response_model=List[ServiceResponse])
async def get_admin_services(
    master: Master = Depends(require_master),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get active services for the authenticated master (paginated)."""
    result = await db.execute(
        select(Service)
        .where(Service.master_id == master.id, Service.is_active == True)
        .order_by(Service.name)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/services/all", response_model=List[ServiceResponse])
async def get_all_admin_services(
    master: Master = Depends(require_master),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all services for the authenticated master (including inactive, paginated)."""
    result = await db.execute(
        select(Service)
        .where(Service.master_id == master.id)
        .order_by(Service.name)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.patch("/services/{service_id}", response_model=ServiceResponse)
async def update_admin_service(
    service_id: int,
    data: ServiceUpdate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update a service belonging to the authenticated master."""
    service = await get_owned_or_404(db, Service, service_id, master.id)
    for field, value in data.model_dump().items():
        if value is not None:
            setattr(service, field, value)
    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=200)
async def delete_admin_service(
    service_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete a service belonging to the authenticated master."""
    service = await get_owned_or_404(db, Service, service_id, master.id)
    await log_action(db, master.id, "delete", "service", service_id, service.name)
    service.is_active = False
    await db.commit()
    return {"detail": "Service deleted"}


# ─── Clients CRUD (admin only) ───────────────────────────────────────────────

@router.get("/clients", response_model=List[ClientResponse])
async def get_admin_clients(
    master: Master = Depends(require_master),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all clients (paginated)."""
    result = await db.execute(
        select(Client)
        .order_by(Client.name)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.delete("/clients/{client_id}", status_code=200)
async def delete_admin_client(
    client_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete a client (only if associated with this master's appointments)."""
    # Check if client belongs to this master
    appt_check = await db.execute(
        select(Appointment.id).where(
            Appointment.client_id == client_id,
            Appointment.master_id == master.id
        ).limit(1)
    )
    if not appt_check.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Клиент не найден или не относится к вам")

    client = await get_or_404(db, Client, client_id)
    await log_action(db, master.id, "delete", "client", client_id, client.name)
    await db.delete(client)
    await db.commit()
    return {"detail": "Клиент удалён"}


@router.post("/clients", response_model=ClientResponse, status_code=201)
async def create_admin_client(
    data: ClientCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new client with duplicate check."""
    # Check phone duplicate
    result = await db.execute(
        select(Client).where(Client.phone == data.phone)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")

    # Check email duplicate
    if data.email:
        result = await db.execute(
            select(Client).where(Client.email == data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")

    new_client = Client(
        name=data.name,
        phone=data.phone,
        email=data.email
    )
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    return new_client


@router.patch("/clients/{client_id}", response_model=ClientResponse)
async def update_admin_client(
    client_id: int,
    data: ClientUpdate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update a client with duplicate check."""
    client = await get_or_404(db, Client, client_id)

    # Check phone duplicate (if changed)
    if data.phone and data.phone != client.phone:
        result = await db.execute(
            select(Client).where(Client.phone == data.phone)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")

    # Check email duplicate (if changed)
    if data.email and data.email != (client.email or ''):
        result = await db.execute(
            select(Client).where(Client.email == data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)

    await db.commit()
    await db.refresh(client)
    return client


# ─── Audit Logs ──────────────────────────────────────────────────────────────

@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    master: Master = Depends(require_master),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs for the authenticated master."""
    query = select(AuditLog).where(AuditLog.master_id == master.id)
    count_query = select(func.count(AuditLog.id)).where(AuditLog.master_id == master.id)

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()

    return AuditLogListResponse(
        total=total,
        logs=[
            AuditLogResponse(
                id=log.id,
                master_id=log.master_id,
                action=log.action,
                entity_type=log.entity_type,
                entity_id=log.entity_id,
                details=log.details,
                ip_address=log.ip_address,
                created_at=log.created_at
            )
            for log in logs
        ]
    )


# ─── CSV Export ──────────────────────────────────────────────────────────────

@router.get("/export/appointments")
async def export_appointments_csv(
    master: Master = Depends(require_master),
    status: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Export appointments to CSV."""
    query = (
        select(
            Appointment,
            Client.name.label('client_name'),
            Client.phone.label('client_phone'),
            Service.name.label('service_name'),
            Service.price.label('service_price')
        )
        .join(Client, Appointment.client_id == Client.id, isouter=True)
        .join(Service, Appointment.service_id == Service.id, isouter=True)
        .where(Appointment.master_id == master.id)
    )

    if status:
        query = query.where(Appointment.status == status)

    query = query.order_by(Appointment.appointment_date.desc())
    result = await db.execute(query)
    rows = result.all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Дата', 'Клиент', 'Телефон', 'Услуга', 'Цена', 'Статус', 'Примечания'])

    for row in rows:
        a = row[0]
        writer.writerow([
            a.id,
            a.appointment_date.strftime('%Y-%m-%d %H:%M') if a.appointment_date else '',
            row[1] or '',
            row[2] or '',
            row[3] or '',
            float(row[4]) if row[4] else 0,
            a.status,
            a.notes or ''
        ])

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=appointments.csv'}
    )


@router.get("/export/clients")
async def export_clients_csv(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Export all clients to CSV."""
    result = await db.execute(
        select(Client)
        .order_by(Client.name)
    )
    clients = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Имя', 'Телефон', 'Email'])

    for client in clients:
        writer.writerow([client.id, client.name, client.phone, client.email or ''])

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=clients.csv'}
    )


# ─── Blocked Slots ───────────────────────────────────────────────────────────

@router.get("/blocked-slots")
async def get_blocked_slots(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get blocked slots for the authenticated master."""
    result = await db.execute(
        select(BlockedSlot)
        .where(BlockedSlot.master_id == master.id)
        .order_by(BlockedSlot.start_dt.desc())
    )
    slots = result.scalars().all()
    return [
        BlockedSlotResponse(
            id=s.id,
            master_id=s.master_id,
            start_dt=s.start_dt,
            end_dt=s.end_dt,
            reason=s.reason,
            created_at=s.created_at
        )
        for s in slots
    ]


@router.post("/blocked-slots", response_model=BlockedSlotResponse, status_code=201)
async def create_blocked_slot(
    data: BlockedSlotCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Block a time slot (no appointments allowed)."""
    if data.start_dt >= data.end_dt:
        raise HTTPException(status_code=422, detail="start_dt must be before end_dt")

    slot = BlockedSlot(
        master_id=master.id,
        start_dt=data.start_dt,
        end_dt=data.end_dt,
        reason=data.reason
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    await log_action(db, master.id, "create", "blocked_slot", slot.id, f"Блокировка: {slot.start_dt} - {slot.end_dt}")
    return slot


@router.delete("/blocked-slots/{slot_id}", status_code=200)
async def delete_blocked_slot(
    slot_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete a blocked slot."""
    slot = await get_owned_or_404(db, BlockedSlot, slot_id, master.id)
    await log_action(db, master.id, "delete", "blocked_slot", slot_id)
    await db.delete(slot)
    await db.commit()
    return {"detail": "Blocked slot deleted"}

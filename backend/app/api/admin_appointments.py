"""Admin appointment CRUD endpoints."""
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timedelta
from app.api.admin_base import (
    get_db, Appointment, Client, Service, Master, require_master,
    get_owned_or_404, log_action, AppointmentWithDetails, AdminBookingCreate,
    AppointmentResponse, AppointmentCreate
)
from sqlalchemy.orm import selectinload

router = APIRouter()


async def _find_or_create_client(db: AsyncSession, phone: str, name: str) -> Client:
    """Helper: find existing client by phone or create new one."""
    from app.schemas.client import normalize_phone
    normalized = normalize_phone(phone)
    result = await db.execute(select(Client).where(Client.phone == normalized))
    client = result.scalar_one_or_none()
    if not client:
        client = Client(name=name, phone=normalized)
        db.add(client)
        await db.commit()
        await db.refresh(client)
    return client


@router.get("/appointments", response_model=List[AppointmentWithDetails])
async def get_admin_appointments(
    master: Master = Depends(require_master),
    status: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments with client and service details.
    Superadmins see all appointments; regular masters see only their own.
    """
    if master.is_admin:
        query = (
            select(Appointment, Client.name.label('client_name'), Client.phone.label('client_phone'),
                   Service.name.label('service_name'), Service.price.label('service_price'),
                   Master.name.label('master_name'))
            .join(Client, Appointment.client_id == Client.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .join(Master, Appointment.master_id == Master.id, isouter=True)
        )
    else:
        query = (
            select(Appointment, Client.name.label('client_name'), Client.phone.label('client_phone'),
                   Service.name.label('service_name'), Service.price.label('service_price'))
            .join(Client, Appointment.client_id == Client.id, isouter=True)
            .join(Service, Appointment.service_id == Service.id, isouter=True)
            .where(Appointment.master_id == master.id)
        )
    if status:
        query = query.where(Appointment.status == status)
    query = query.order_by(Appointment.appointment_date.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    rows = result.all()
    
    if master.is_admin and len(rows) > 0 and rows[0][5] is not None:  # has master_name column
        return [
            AppointmentWithDetails(
                id=row[0].id, master_id=row[0].master_id, service_id=row[0].service_id,
                client_id=row[0].client_id, appointment_date=row[0].appointment_date,
                status=row[0].status, notes=row[0].notes,
                client_name=row[1], client_phone=row[2], service_name=row[3], service_price=row[4]
            ) for row in rows
        ]
    else:
        return [
            AppointmentWithDetails(
                id=row[0].id, master_id=row[0].master_id, service_id=row[0].service_id,
                client_id=row[0].client_id, appointment_date=row[0].appointment_date,
                status=row[0].status, notes=row[0].notes,
                client_name=row[1], client_phone=row[2], service_name=row[3], service_price=row[4]
            ) for row in rows
        ]


@router.post("/appointments", response_model=AppointmentResponse, status_code=201)
async def create_appointment(
    data: AppointmentCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new appointment."""
    if data.master_id != master.id:
        raise HTTPException(status_code=403, detail="Not your master")
    client = await _find_or_create_client(db, data.client_phone, data.client_name)
    new_appointment = Appointment(
        master_id=data.master_id, service_id=data.service_id, client_id=client.id,
        appointment_date=data.appointment_date, status="pending", notes=data.notes
    )
    db.add(new_appointment)
    await log_action(db, master.id, "create", "appointment", new_appointment.id, f"Клиент: {client.name}", level="info")
    await db.commit()
    await db.refresh(new_appointment)
    return new_appointment


@router.post("/appointments/book", response_model=AppointmentResponse, status_code=201)
async def book_appointment(
    data: AdminBookingCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Book an appointment from admin panel (select client from DB)."""
    service_result = await db.execute(
        select(Service).where(Service.id == data.service_id, Service.master_id == master.id)
    )
    service = service_result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Услуга не найдена")

    client_result = await db.execute(select(Client).where(Client.id == data.client_id))
    client = client_result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Клиент не найден")

    service_end = data.appointment_date + timedelta(minutes=service.duration_minutes)
    conflict_result = await db.execute(
        select(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(
            Appointment.master_id == master.id, Appointment.status != "cancelled",
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
        master_id=master.id, service_id=data.service_id, client_id=data.client_id,
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
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments for a date range."""
    start_dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=None)
    end_dt = datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=None)
    query = (
        select(Appointment)
        .options(selectinload(Appointment.client), selectinload(Appointment.service))
        .where(Appointment.master_id == master.id,
               Appointment.appointment_date >= start_dt, Appointment.appointment_date <= end_dt)
        .order_by(Appointment.appointment_date)
    )
    result = await db.execute(query)
    appointments = result.scalars().all()
    return [
        {"id": a.id, "client_name": a.client.name if a.client else "Unknown",
         "client_phone": a.client.phone if a.client else "",
         "service_name": a.service.name if a.service else "",
         "appointment_date": a.appointment_date.isoformat(), "status": a.status}
        for a in appointments
    ]


@router.patch("/appointments/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Confirm an appointment."""
    appointment = await get_owned_or_404(db, Appointment, appointment_id, master.id)
    appointment.status = "confirmed"
    await log_action(db, master.id, "confirm", "appointment", appointment.id, "Статус изменён на confirmed", level="info")
    await db.commit()
    await db.refresh(appointment)
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
    await log_action(db, master.id, "cancel", "appointment", appointment.id, f"Причина: {reason}", level="warning")
    await db.commit()
    await db.refresh(appointment)
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
    await log_action(db, master.id, "complete", "appointment", appointment.id, level="info")
    await db.commit()
    await db.refresh(appointment)
    return appointment


@router.delete("/appointments/{appointment_id}", status_code=204)
async def delete_appointment(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete an appointment."""
    appointment = await get_owned_or_404(db, Appointment, appointment_id, master.id)
    await log_action(db, master.id, "delete", "appointment", appointment_id, level="warning")
    await db.delete(appointment)
    await db.commit()
    return None


@router.patch("/appointments/{appointment_id}/no-show")
async def mark_no_show(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Mark an appointment as no-show. Increments client's no_show_count."""
    appointment = await get_owned_or_404(db, Appointment, appointment_id, master.id)
    appointment.status = "cancelled"
    appointment.notes = f"{appointment.notes}\n\nНеявка" if appointment.notes else "Неявка"
    await log_action(db, master.id, "no-show", "appointment", appointment_id, level="warning")

    # Increment no-show count for the client
    if appointment.client_id:
        client_result = await db.execute(select(Client).where(Client.id == appointment.client_id))
        client = client_result.scalar_one_or_none()
        if client:
            client.no_show_count = (client.no_show_count or 0) + 1

    await db.commit()
    await db.refresh(appointment)
    return appointment

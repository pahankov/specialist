from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from datetime import datetime, timedelta
from app.database import get_db
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.client import Client
from app.models.master import Master
from app.schemas.appointment import AppointmentCreate, AppointmentResponse, AvailableDay, AvailableSlot, PublicBookingCreate

router = APIRouter()

@router.get("/", response_model=List[AppointmentResponse])
async def get_appointments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Appointment))
    appointments = result.scalars().all()
    return appointments

@router.get("/available-days", response_model=List[AvailableDay])
async def get_available_days(
    master_id: int = Query(...),
    days_ahead: int = Query(14),
    db: AsyncSession = Depends(get_db)
):
    # Simplified: return next N days as available
    available_days = []
    today = datetime.now().date()
    
    for i in range(days_ahead):
        check_date = today + timedelta(days=i)
        # Skip Sundays (day_of_week=6)
        if check_date.weekday() != 6:
            available_days.append({
                "date": check_date.isoformat(),
                "day_of_week": check_date.weekday()
            })
    
    return available_days

@router.get("/available-slots", response_model=List[AvailableSlot])
async def get_available_slots(
    master_id: int = Query(...),
    service_id: int = Query(...),
    date: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    # Get service duration
    service_result = await db.execute(select(Service).where(Service.id == service_id))
    service = service_result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    # Simplified: generate slots from 10:00 to 18:00
    slots = []
    appointment_datetime = datetime.fromisoformat(date)
    start_hour = 10
    end_hour = 18
    
    current_time = appointment_datetime.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end_time = appointment_datetime.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    
    while current_time + timedelta(minutes=service.duration_minutes) <= end_time:
        slots.append({
            "start": current_time.isoformat(),
            "end": (current_time + timedelta(minutes=service.duration_minutes)).isoformat()
        })
        current_time = current_time + timedelta(hours=1)
    
    return slots

@router.post("/public", response_model=AppointmentResponse, status_code=201)
async def public_booking(booking: PublicBookingCreate, db: AsyncSession = Depends(get_db)):
    # Check or create client
    client_result = await db.execute(select(Client).where(Client.phone == booking.client_phone))
    client = client_result.scalar_one_or_none()
    
    if not client:
        # Create new client
        client = Client(
            name=booking.client_name,
            phone=booking.client_phone
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)
    
    # Create appointment
    appointment = Appointment(
        master_id=booking.master_id,
        service_id=booking.service_id,
        client_id=client.id,
        appointment_date=booking.appointment_date,
        status="pending"
    )
    
    db.add(appointment)
    await db.commit()
    await db.refresh(appointment)
    
    return appointment

@router.post("/", response_model=AppointmentResponse, status_code=201)
async def create_appointment(appointment: AppointmentCreate, db: AsyncSession = Depends(get_db)):
    # Check or create client
    client_result = await db.execute(select(Client).where(Client.phone == appointment.client_phone))
    client = client_result.scalar_one_or_none()
    
    if not client:
        client = Client(
            name=appointment.client_name,
            phone=appointment.client_phone
        )
        db.add(client)
        await db.commit()
        await db.refresh(client)
    
    # Create appointment
    new_appointment = Appointment(
        master_id=appointment.master_id,
        service_id=appointment.service_id,
        client_id=client.id,
        appointment_date=appointment.appointment_date,
        status="confirmed"
    )
    
    db.add(new_appointment)
    await db.commit()
    await db.refresh(new_appointment)
    
    return new_appointment

@router.delete("/{appointment_id}", status_code=204)
async def delete_appointment(appointment_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalar_one_or_none()
    
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
    
    await db.delete(appointment)
    await db.commit()
    return None
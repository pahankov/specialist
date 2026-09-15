"""Admin API endpoints for master dashboard."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from typing import List, Optional
from datetime import datetime, date, timedelta
from app.database import get_db
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.models.master import Master
from app.schemas.appointment import AppointmentResponse
from app.api.dependencies import require_master

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
        .where(Appointment.master_id == master.id)
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()

    # Upcoming appointments (next 7 days)
    week_from_now = datetime.now() + timedelta(days=7)
    upcoming_result = await db.execute(
        select(Appointment)
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
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status,
                "service_id": a.service_id
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


@router.get("/appointments", response_model=List[AppointmentResponse])
async def get_admin_appointments(
    master: Master = Depends(require_master),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get appointments for the authenticated master."""
    query = select(Appointment).where(Appointment.master_id == master.id)

    if status:
        query = query.where(Appointment.status == status)

    query = query.order_by(Appointment.appointment_date.desc()).limit(limit)
    result = await db.execute(query)
    appointments = result.scalars().all()

    return appointments


@router.patch("/appointments/{appointment_id}/confirm")
async def confirm_appointment(
    appointment_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Confirm an appointment."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.master_id == master.id
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = "confirmed"
    await db.commit()
    await db.refresh(appointment)

    return {"detail": "Appointment confirmed", "appointment": appointment}


@router.patch("/appointments/{appointment_id}/cancel")
async def cancel_appointment(
    appointment_id: int,
    reason: Optional[str] = Query(None),
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Cancel an appointment."""
    result = await db.execute(
        select(Appointment).where(
            Appointment.id == appointment_id,
            Appointment.master_id == master.id
        )
    )
    appointment = result.scalar_one_or_none()

    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")

    appointment.status = "cancelled"
    if reason:
        appointment.notes = reason
    await db.commit()
    await db.refresh(appointment)

    return {"detail": "Appointment cancelled", "appointment": appointment}


@router.post("/services", response_model=dict, status_code=201)
async def create_service(
    service_data: dict,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new service for the authenticated master."""
    from app.schemas.service import ServiceCreate

    # Validate data
    required_fields = ["name", "duration_minutes", "price"]
    for field in required_fields:
        if field not in service_data:
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")

    service = Service(
        master_id=master.id,
        name=service_data["name"],
        description=service_data.get("description"),
        duration_minutes=service_data["duration_minutes"],
        price=service_data["price"]
    )

    db.add(service)
    await db.commit()
    await db.refresh(service)
    return service


@router.patch("/services/{service_id}", response_model=dict)
async def update_service(
    service_id: int,
    service_data: dict,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update a service for the authenticated master."""
    result = await db.execute(
        select(Service).where(
            Service.id == service_id,
            Service.master_id == master.id
        )
    )
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    for key, value in service_data.items():
        if value is not None and hasattr(service, key):
            setattr(service, key, value)

    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=200)
async def delete_service(
    service_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete a service for the authenticated master."""
    result = await db.execute(
        select(Service).where(
            Service.id == service_id,
            Service.master_id == master.id
        )
    )
    service = result.scalar_one_or_none()

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    await db.delete(service)
    await db.commit()
    return {"detail": "Service deleted"}


@router.get("/working-hours")
async def get_working_hours(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get working hours for the authenticated master."""
    from app.models.working_hour import WorkingHour

    result = await db.execute(
        select(WorkingHour).where(WorkingHour.master_id == master.id)
        .order_by(WorkingHour.day_of_week)
    )
    hours = result.scalars().all()

    return [
        {
            "id": h.id,
            "master_id": h.master_id,
            "day_of_week": h.day_of_week,
            "start_time": h.start_time.isoformat() if h.start_time else None,
            "end_time": h.end_time.isoformat() if h.end_time else None
        }
        for h in hours
    ]


@router.post("/working-hours", status_code=201)
async def create_working_hour(
    hour_data: dict,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create working hours for the authenticated master."""
    from app.models.working_hour import WorkingHour
    from datetime import time

    required_fields = ["day_of_week", "start_time", "end_time"]
    for field in required_fields:
        if field not in hour_data:
            raise HTTPException(status_code=422, detail=f"Missing field: {field}")

    # Parse time strings
    start_parts = hour_data["start_time"].split(":")
    end_parts = hour_data["end_time"].split(":")

    hour = WorkingHour(
        master_id=master.id,
        day_of_week=hour_data["day_of_week"],
        start_time=time(int(start_parts[0]), int(start_parts[1])),
        end_time=time(int(end_parts[0]), int(end_parts[1]))
    )

    db.add(hour)
    await db.commit()
    await db.refresh(hour)

    return {
        "id": hour.id,
        "master_id": hour.master_id,
        "day_of_week": hour.day_of_week,
        "start_time": hour.start_time.isoformat(),
        "end_time": hour.end_time.isoformat()
    }


@router.delete("/working-hours/{hour_id}", status_code=200)
async def delete_working_hour(
    hour_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete working hours for the authenticated master."""
    from app.models.working_hour import WorkingHour

    result = await db.execute(
        select(WorkingHour).where(
            WorkingHour.id == hour_id,
            WorkingHour.master_id == master.id
        )
    )
    hour = result.scalar_one_or_none()

    if not hour:
        raise HTTPException(status_code=404, detail="Working hour not found")

    await db.delete(hour)
    await db.commit()
    return {"detail": "Working hour deleted"}

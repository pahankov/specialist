"""Dashboard and monthly statistics endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from app.api.admin_base import (
    get_db, Appointment, Client, Service, Master, require_master
)

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics.
    For regular masters: returns their own stats.
    For superadmins (is_admin=True): returns global stats across all masters.
    """
    # Superadmin gets global stats
    if master.is_admin:
        return await _get_global_stats(db)
    
    # Regular master gets their own stats
    return await _get_master_stats(master, db)


async def _get_master_stats(master: Master, db: AsyncSession):
    """Get statistics for a specific master."""
    result = await db.execute(
        select(Appointment.status, func.count(Appointment.id))
        .where(Appointment.master_id == master.id)
        .group_by(Appointment.status)
    )
    status_counts = {row[0]: row[1] for row in result.all()}

    total_result = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.master_id == master.id)
    )
    total_appointments = total_result.scalar() or 0

    client_result = await db.execute(
        select(func.count(Client.id)).where(
            Client.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == master.id)
            )
        )
    )
    total_clients = client_result.scalar() or 0

    service_result = await db.execute(
        select(func.count(Service.id)).where(Service.master_id == master.id)
    )
    total_services = service_result.scalar() or 0

    recent_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client), selectinload(Appointment.service))
        .where(Appointment.master_id == master.id)
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()

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

    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master.id, Appointment.status == "completed")
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
                "id": a.id, "client_id": a.client_id,
                "client_name": a.client.name if a.client else None,
                "client_phone": a.client.phone if a.client else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status, "service_id": a.service_id,
                "service_name": a.service.name if a.service else None,
                "service_price": float(a.service.price) if a.service else 0
            } for a in recent_appointments
        ],
        "upcoming_appointments": [
            {"id": a.id, "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None, "status": a.status}
            for a in upcoming_appointments
        ]
    }


async def _get_global_stats(db: AsyncSession):
    """Get global statistics across all masters (superadmin only)."""
    # Total masters
    total_masters_result = await db.execute(select(func.count(Master.id)))
    total_masters = total_masters_result.scalar() or 0
    
    active_masters_result = await db.execute(
        select(func.count(Master.id)).where(Master.is_active == True)
    )
    active_masters = active_masters_result.scalar() or 0

    # Total appointments by status
    status_result = await db.execute(
        select(Appointment.status, func.count(Appointment.id))
        .group_by(Appointment.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}
    total_appointments = sum(status_counts.values())

    # Total clients
    total_clients_result = await db.execute(select(func.count(Client.id)))
    total_clients = total_clients_result.scalar() or 0

    # Total services
    total_services_result = await db.execute(select(func.count(Service.id)))
    total_services = total_services_result.scalar() or 0

    # Total revenue
    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(Appointment.status == "completed")
    )
    total_revenue = float(revenue_result.scalar() or 0)

    # Recent appointments
    recent_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client), selectinload(Appointment.service), selectinload(Appointment.master))
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()

    # Upcoming appointments
    week_from_now = datetime.now() + timedelta(days=7)
    upcoming_result = await db.execute(
        select(Appointment)
        .where(
            Appointment.appointment_date >= datetime.now(),
            Appointment.appointment_date <= week_from_now,
            Appointment.status != "cancelled"
        )
        .order_by(Appointment.appointment_date.asc())
    )
    upcoming_appointments = upcoming_result.scalars().all()

    return {
        "total_masters": total_masters,
        "active_masters": active_masters,
        "total_appointments": total_appointments,
        "status_counts": status_counts,
        "total_clients": total_clients,
        "total_services": total_services,
        "total_revenue": total_revenue,
        "recent_appointments": [
            {
                "id": a.id,
                "master_name": a.master.name if a.master else None,
                "client_name": a.client.name if a.client else None,
                "client_phone": a.client.phone if a.client else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status,
                "service_name": a.service.name if a.service else None,
                "service_price": float(a.service.price) if a.service else 0
            } for a in recent_appointments
        ],
        "upcoming_appointments": [
            {
                "id": a.id,
                "master_name": a.master.name if a.master else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status
            } for a in upcoming_appointments
        ]
    }


@router.get("/monthly-stats")
async def get_monthly_stats(
    year: int = Query(..., description="Year"),
    month: int = Query(..., description="Month (1-12)"),
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific month."""
    start_dt = datetime(year, month, 1)
    end_dt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    confirmed_result = await db.execute(
        select(func.count(Appointment.id))
        .where(Appointment.master_id == master.id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status.in_(["confirmed", "completed"]))
    )
    confirmed_count = confirmed_result.scalar() or 0

    duration_result = await db.execute(
        select(func.sum(Service.duration_minutes))
        .select_from(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master.id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status.in_(["confirmed", "completed"]))
    )
    total_minutes = duration_result.scalar() or 0

    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master.id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status == "completed")
    )
    month_revenue = revenue_result.scalar() or 0

    return {
        "confirmed_appointments": confirmed_count,
        "total_minutes": float(total_minutes),
        "total_hours": round(total_minutes / 60, 1),
        "revenue": float(month_revenue)
    }

"""Dashboard and monthly statistics endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from datetime import timedelta

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.models.user import User
from app.models.master_profile import MasterProfile
from app.dependencies.auth import require_master
from app.utils import utcnow

router = APIRouter()


@router.get("/dashboard")
async def get_dashboard(
    master: User = Depends(require_master),
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


async def _get_master_stats(master: User, db: AsyncSession):
    """Get statistics for a specific master."""
    result = await db.execute(
        select(Appointment.status, func.count(Appointment.id))
        .where(Appointment.master_id == master.master_profile.id)
        .group_by(Appointment.status)
    )
    status_counts = {row[0]: row[1] for row in result.all()}

    total_result = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.master_id == master.master_profile.id)
    )
    total_appointments = total_result.scalar() or 0

    client_result = await db.execute(
        select(func.count(ClientProfile.id)).where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == master.master_profile.id)
            )
        )
    )
    total_clients = client_result.scalar() or 0

    service_result = await db.execute(
        select(func.count(Service.id)).where(Service.master_id == master.master_profile.id)
    )
    total_services = service_result.scalar() or 0

    recent_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client_profile), selectinload(Appointment.service))
        .where(Appointment.master_id == master.master_profile.id)
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()

    week_from_now = utcnow() + timedelta(days=7)
    upcoming_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client_profile), selectinload(Appointment.service))
        .where(
            Appointment.master_id == master.master_profile.id,
            Appointment.appointment_date >= utcnow(),
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
        .where(Appointment.master_id == master.master_profile.id, Appointment.status == "completed")
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
                "client_name": a.client_profile.user.name if a.client_profile else None,
                "client_phone": a.client_profile.user.phone if a.client_profile else None,
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
    # Total masters (exclude superadmins — they are platform admins, not service providers)
    total_masters_result = await db.execute(
        select(func.count(MasterProfile.id))
        .join(MasterProfile.user)
        .where(User.role == "MASTER")
    )
    total_masters = total_masters_result.scalar() or 0
    
    active_masters_result = await db.execute(
        select(func.count(MasterProfile.id))
        .join(MasterProfile.user)
        .where(MasterProfile.is_active == True, User.role == "MASTER")
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
    total_clients_result = await db.execute(select(func.count(ClientProfile.id)))
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
        .options(selectinload(Appointment.client_profile), selectinload(Appointment.service), selectinload(Appointment.master_profile))
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()

    # Upcoming appointments
    week_from_now = utcnow() + timedelta(days=7)
    upcoming_result = await db.execute(
        select(Appointment)
        .where(
            Appointment.appointment_date >= utcnow(),
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
                "master_name": a.master_profile.user.name if a.master_profile else None,
                "client_name": a.client_profile.user.name if a.client_profile else None,
                "client_phone": a.client_profile.user.phone if a.client_profile else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status,
                "service_name": a.service.name if a.service else None,
                "service_price": float(a.service.price) if a.service else 0
            } for a in recent_appointments
        ],
        "upcoming_appointments": [
            {
                "id": a.id,
                "master_name": a.master_profile.user.name if a.master_profile else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status
            } for a in upcoming_appointments
        ]
    }


@router.get("/monthly-stats")
async def get_monthly_stats(
    year: int = Query(..., description="Year"),
    month: int = Query(..., description="Month (1-12)"),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific month."""
    start_dt = datetime(year, month, 1)
    end_dt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    confirmed_result = await db.execute(
        select(func.count(Appointment.id))
        .where(Appointment.master_id == master.master_profile.id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status.in_(["confirmed", "completed"]))
    )
    confirmed_count = confirmed_result.scalar() or 0

    duration_result = await db.execute(
        select(func.sum(Service.duration_minutes))
        .select_from(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master.master_profile.id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status.in_(["confirmed", "completed"]))
    )
    total_minutes = duration_result.scalar() or 0

    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master.master_profile.id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status == "completed")
    )
    month_revenue = revenue_result.scalar() or 0

    return {
        "confirmed_appointments": confirmed_count,
        "total_minutes": float(total_minutes),
        "total_hours": round(total_minutes / 60, 1),
        "revenue": float(month_revenue)
    }

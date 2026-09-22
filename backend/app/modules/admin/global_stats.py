"""Global statistics endpoint for superadmins."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta

from app.database import get_db
from app.models.user import User
from app.models.master_profile import MasterProfile
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.modules.auth.dependencies import require_super_admin
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/global-stats")
async def get_global_stats(
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get global statistics across all masters (superadmin only)."""
    # Total masters (active and admin counts)
    total_masters_result = await db.execute(select(func.count(MasterProfile.id)))
    total_masters = total_masters_result.scalar() or 0
    
    active_masters_result = await db.execute(
        select(func.count(MasterProfile.id)).where(MasterProfile.is_active == True)
    )
    active_masters = active_masters_result.scalar() or 0
    
    admin_masters_result = await db.execute(
        select(func.count(MasterProfile.id)).where(MasterProfile.user.has(role='admin'))
    )
    admin_masters = admin_masters_result.scalar() or 0
    
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
    
    # Total revenue (completed appointments)
    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(Appointment.status == "completed")
    )
    total_revenue = float(revenue_result.scalar() or 0)
    
    # Recent appointments (last 10 across all masters)
    recent_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client_profile), selectinload(Appointment.service), selectinload(Appointment.master_profile))
        .order_by(Appointment.appointment_date.desc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()
    
    # Upcoming appointments (next 7 days)
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
    
    # Revenue by status
    revenue_by_status = await db.execute(
        select(Appointment.status, func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .group_by(Appointment.status)
    )
    revenue_by_status = {row[0]: float(row[1] or 0) for row in revenue_by_status.all()}
    
    return {
        "total_masters": total_masters,
        "active_masters": active_masters,
        "admin_masters": admin_masters,
        "total_appointments": total_appointments,
        "status_counts": status_counts,
        "total_clients": total_clients,
        "total_services": total_services,
        "total_revenue": total_revenue,
        "revenue_by_status": revenue_by_status,
        "recent_appointments": [
            {
                "id": a.id,
                "master_name": a.master_profile.user.name if a.master_profile else None,
                "client_name": a.client_profile.user.name if a.client_profile else None,
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

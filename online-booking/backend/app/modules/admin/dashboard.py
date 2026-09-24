"""Dashboard and monthly statistics endpoints."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from datetime import timedelta, datetime
from typing import Optional

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.models.user import User
from app.models.master_profile import MasterProfile
from sqlalchemy.orm import aliased
from app.dependencies.auth import require_master
from app.utils import utcnow
from app.services.cache import cache_service

router = APIRouter()

# Aliases for master user lookups
_MasterUser = aliased(User, name="master_user")


@router.get("/dashboard")
async def get_dashboard(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get dashboard statistics.
    For regular masters: returns their own stats.
    For superadmins (is_admin=True): returns global stats across all masters.
    
    Uses Redis cache with 5-minute TTL for superadmin stats.
    """
    if master.is_admin:
        cache_key = f"admin:dashboard:global"
        
        # Try cache first
        cached = cache_service.get(cache_key)
        if cached is not None:
            return cached
        
        # Compute and cache
        stats = await _get_global_stats(db)
        cache_service.set(cache_key, stats, ttl=300)  # 5 minutes
        return stats
    
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


@router.post("/dashboard/cache/clear")
async def clear_dashboard_cache(
    master: User = Depends(require_master)
):
    """Clear dashboard cache (superadmin only)."""
    if not master.is_admin:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Only superadmin can clear cache")
    
    cache_service.invalidate_pattern("admin:dashboard:*")
    return {"detail": "Dashboard cache cleared"}


@router.get("/revenue-breakdown")
async def get_revenue_breakdown(
    master: User = Depends(require_master),
    by_master: bool = Query(False, description="Group by master"),
    by_service: bool = Query(False, description="Group by service"),
    master_id: Optional[int] = Query(None, description="Filter by master ID (superadmin only)"),
    date_from: Optional[str] = Query(None, description="Filter by date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db)
):
    """Get revenue breakdown grouped by master, service, or overall."""
    from datetime import datetime as dt_datetime
    
    # Base filter: completed appointments with their services
    base_conditions = [Appointment.status == "completed"]
    
    if date_from:
        dt_from = dt_datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=None)
        base_conditions.append(Appointment.appointment_date >= dt_from)
    if date_to:
        dt_to = dt_datetime.strptime(date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=None)
        base_conditions.append(Appointment.appointment_date <= dt_to)
    
    # For non-admin masters, filter by their master_id
    if not master.is_admin:
        result = await db.execute(
            select(MasterProfile).where(MasterProfile.user_id == master.id)
        )
        mp = result.scalar_one_or_none()
        if not mp:
            return {"breakdown": [], "total_revenue": 0}
        base_conditions.append(Appointment.master_id == mp.id)
    elif master_id is not None:
        # Superadmin can filter by specific master
        base_conditions.append(Appointment.master_id == master_id)
    
    # Build query based on grouping
    if by_master:
        # Group by master
        query = (
            select(
                _MasterUser.name.label('name'),
                func.sum(Service.price).label('revenue'),
                func.count(Appointment.id).label('count')
            )
            .select_from(Appointment)
            .join(Service, Appointment.service_id == Service.id)
            .join(MasterProfile, Appointment.master_id == MasterProfile.id)
            .join(_MasterUser, MasterProfile.user_id == _MasterUser.id)
            .where(*base_conditions)
            .group_by(_MasterUser.name)
            .order_by(func.sum(Service.price).desc())
        )
    elif by_service:
        # Group by service
        query = (
            select(
                Service.name.label('name'),
                func.sum(Service.price).label('revenue'),
                func.count(Appointment.id).label('count')
            )
            .select_from(Appointment)
            .join(Service, Appointment.service_id == Service.id)
            .where(*base_conditions)
            .group_by(Service.id, Service.name)
            .order_by(func.sum(Service.price).desc())
        )
    else:
        # Overall revenue
        total_result = await db.execute(
            select(func.sum(Service.price))
            .select_from(Appointment)
            .join(Service, Appointment.service_id == Service.id)
            .where(*base_conditions)
        )
        total_revenue = float(total_result.scalar() or 0)
        return {"breakdown": [], "total_revenue": total_revenue}
    
    result = await db.execute(query)
    breakdown = [
        {"name": row[0], "revenue": float(row[1]), "count": row[2]}
        for row in result.all()
    ]
    
    total_revenue = sum(item['revenue'] for item in breakdown)
    return {"breakdown": breakdown, "total_revenue": total_revenue}

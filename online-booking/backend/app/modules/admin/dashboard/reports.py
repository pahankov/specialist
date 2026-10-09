"""Dashboard reports: monthly stats, revenue breakdown, cache management."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import aliased
from datetime import datetime
from typing import Optional

from app.database import get_db
from app.models.appointment import Appointment
from app.models.service import Service
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.dependencies.auth import require_master
from app.modules.admin.helpers import get_master_profile_id
from app.services.cache import cache_service
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Aliases for master user lookups
_MasterUser = aliased(User, name="master_user")


@router.get("/monthly-stats")
async def get_monthly_stats(
    year: int = Query(..., description="Year"),
    month: int = Query(..., description="Month (1-12)"),
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
    master_id: Optional[int] = Query(None, description="Master profile ID (superadmin only)"),
):
    """Get statistics for a specific month."""
    logger.info("Get monthly stats: master=%s, year=%d, month=%d, master_id=%s",
                master.id, year, month, master_id)
    if master.role == UserRole.ADMIN:
        if master_id is None:
            return {"confirmed_appointments": 0, "total_minutes": 0.0,
                    "total_hours": 0.0, "revenue": 0.0}
        target = await db.execute(
            select(MasterProfile).where(MasterProfile.id == master_id)
        )
        if target.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Мастер не найден")
        mp_id = master_id
    else:
        mp_id = await get_master_profile_id(db, master)
    start_dt = datetime(year, month, 1)
    end_dt = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

    confirmed_result = await db.execute(
        select(func.count(Appointment.id))
        .where(Appointment.master_id == mp_id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status.in_(["confirmed", "completed"]))
    )
    confirmed_count = confirmed_result.scalar() or 0

    duration_result = await db.execute(
        select(func.sum(Service.duration_minutes))
        .select_from(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == mp_id, Appointment.appointment_date >= start_dt,
               Appointment.appointment_date < end_dt, Appointment.status.in_(["confirmed", "completed"]))
    )
    total_minutes = duration_result.scalar() or 0

    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment).join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == mp_id, Appointment.appointment_date >= start_dt,
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
        raise HTTPException(status_code=403, detail="Only superadmin can clear cache")

    await cache_service.invalidate_pattern("admin:dashboard:*")
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

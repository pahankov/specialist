"""Dashboard overview: main stats (master-scoped or global with Redis cache)."""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload, joinedload, aliased

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.models.user import User
from app.models.master_profile import MasterProfile
from app.dependencies.auth import require_master
from app.utils import localnow_naive
from app.services.cache import cache_service
from app.modules.admin.helpers import get_master_profile_id
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

# Aliases for master user lookups
_MasterUser = aliased(User, name="master_user")


@router.get("/dashboard")
async def get_dashboard(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
    period: str = Query(default="all", description="all|month|today|custom"),
    date_from: Optional[str] = Query(default=None, description="Custom start (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(default=None, description="Custom end (YYYY-MM-DD)"),
):
    """Get dashboard statistics.
    For regular masters: returns their own stats.
    For superadmins (is_admin=True): returns global stats across all masters.

    `period` scopes appointment-based metrics (counts, revenue, top
    clients) to a date window; catalog counts (clients, services,
    masters) and the upcoming lists stay global. Uses Redis cache
    with 5-minute TTL for superadmin stats.
    """
    logger.info("Get dashboard for master %s (is_admin=%s, period=%s)", master.id, master.is_admin, period)
    bounds = _resolve_period(period, date_from, date_to)
    if master.is_admin:
        cache_key = f"admin:dashboard:global:{bounds[0] or '-'}:{bounds[1] or '-'}"

        # Try cache first
        cached = await cache_service.get(cache_key)
        if cached is not None:
            return cached

        # Compute and cache
        stats = await _get_global_stats(db, bounds)
        await cache_service.set(cache_key, stats, ttl=300)  # 5 minutes
        return stats

    return await _get_master_stats(master, db, bounds)


def _resolve_period(period: str, date_from: Optional[str],
                    date_to: Optional[str]) -> tuple[Optional[datetime], Optional[datetime]]:
    """Map (period, date_from, date_to) to an inclusive [start, end) window.

    Bounds are naive local datetimes (appointments are stored naive).
    """
    now = localnow_naive()
    if period == "all":
        return None, None
    if period == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)
    if period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    if period == "custom":
        try:
            start = datetime.strptime(date_from, "%Y-%m-%d") if date_from else None
            end = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1) if date_to else None
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Даты — в формате ГГГГ-ММ-ДД")
        if start is not None and end is not None and start >= end:
            raise HTTPException(status_code=400, detail="Дата начала позже даты конца")
        return start, end
    raise HTTPException(status_code=400, detail="Период: all|month|today|custom")


def _apply_bounds(query, start: Optional[datetime], end: Optional[datetime]):
    """Narrow an appointment query to the dashboard period window."""
    if start is not None:
        query = query.where(Appointment.appointment_date >= start)
    if end is not None:
        query = query.where(Appointment.appointment_date < end)
    return query


async def _get_master_stats(master: User, db: AsyncSession,
                            bounds: tuple[Optional[datetime], Optional[datetime]]):
    """Get statistics for a specific master."""
    mp_id = await get_master_profile_id(db, master)
    start, end = bounds

    result = await db.execute(
        _apply_bounds(
            select(Appointment.status, func.count(Appointment.id))
            .where(Appointment.master_id == mp_id)
            .group_by(Appointment.status),
            start, end,
        )
    )
    status_counts = {row[0]: row[1] for row in result.all()}

    total_result = await db.execute(
        _apply_bounds(
            select(func.count(Appointment.id)).where(Appointment.master_id == mp_id),
            start, end,
        )
    )
    total_appointments = total_result.scalar() or 0

    client_result = await db.execute(
        select(func.count(ClientProfile.id)).where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == mp_id)
            )
        )
    )
    total_clients = client_result.scalar() or 0

    service_result = await db.execute(
        select(func.count(Service.id)).where(Service.master_id == mp_id)
    )
    total_services = service_result.scalar() or 0

    recent_result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client_profile).joinedload(ClientProfile.user),
            selectinload(Appointment.service),
        )
        .where(
            Appointment.master_id == mp_id,
            Appointment.appointment_date >= localnow_naive(),
            Appointment.status.in_(["pending", "confirmed"]),
        )
        .order_by(Appointment.appointment_date.asc())
        .limit(5)
    )
    recent_appointments = recent_result.scalars().all()

    week_from_now = localnow_naive() + timedelta(days=7)
    upcoming_result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client_profile).joinedload(ClientProfile.user),
            selectinload(Appointment.service),
        )
        .where(
            Appointment.master_id == mp_id,
            Appointment.appointment_date >= localnow_naive(),
            Appointment.appointment_date <= week_from_now,
            Appointment.status != "cancelled"
        )
        .order_by(Appointment.appointment_date.asc())
    )
    upcoming_appointments = upcoming_result.scalars().all()

    revenue_result = await db.execute(
        _apply_bounds(
            select(func.sum(func.coalesce(Appointment.price, Service.price)))
            .select_from(Appointment)
            .outerjoin(Service, Appointment.service_id == Service.id)
            .where(Appointment.master_id == mp_id, Appointment.status == "completed"),
            start, end,
        )
    )
    total_revenue = revenue_result.scalar() or 0

    top_result = await db.execute(
        _apply_bounds(
            select(
                ClientProfile.id,
                User.name,
                func.count(Appointment.id).label("visits"),
                func.sum(func.coalesce(Appointment.price, Service.price)).label("spent"),
            )
            .select_from(Appointment)
            .join(ClientProfile, Appointment.client_id == ClientProfile.id)
            .join(User, ClientProfile.user_id == User.id)
            .outerjoin(Service, Appointment.service_id == Service.id)
            .where(Appointment.master_id == mp_id, Appointment.status == "completed")
            .group_by(ClientProfile.id, User.name)
            .order_by(func.sum(func.coalesce(Appointment.price, Service.price)).desc())
            .limit(5),
            start, end,
        )
    )
    top_clients = [
        {"id": r[0], "name": r[1], "visits": r[2], "spent": float(r[3] or 0)}
        for r in top_result.all()
    ]

    return {
        "total_appointments": total_appointments,
        "status_counts": status_counts,
        "total_clients": total_clients,
        "total_services": total_services,
        "total_revenue": float(total_revenue),
        "top_clients": top_clients,
        "recent_appointments": [
            {
                "id": a.id, "client_id": a.client_id,
                "client_name": a.client_profile.user.name if a.client_profile else None,
                "client_phone": a.client_profile.user.phone if a.client_profile else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status, "service_id": a.service_id,
                "service_name": a.bundle_name or (a.service.name if a.service else None),
                "service_price": float(a.price) if a.price is not None
                else (float(a.service.price) if a.service else 0)
            } for a in recent_appointments
        ],
        "upcoming_appointments": [
            {"id": a.id, "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None, "status": a.status}
            for a in upcoming_appointments
        ]
    }


async def _get_global_stats(db: AsyncSession,
                            bounds: tuple[Optional[datetime], Optional[datetime]]):
    """Get global statistics across all masters (superadmin only)."""
    start, end = bounds
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
        .where(MasterProfile.is_active == True, User.role == "MASTER")  # noqa: E712
    )
    active_masters = active_masters_result.scalar() or 0

    # Total appointments by status
    status_result = await db.execute(
        _apply_bounds(
            select(Appointment.status, func.count(Appointment.id))
            .group_by(Appointment.status),
            start, end,
        )
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
        _apply_bounds(
            select(func.sum(func.coalesce(Appointment.price, Service.price)))
            .select_from(Appointment)
            .outerjoin(Service, Appointment.service_id == Service.id)
            .where(Appointment.status == "completed"),
            start, end,
        )
    )
    total_revenue = float(revenue_result.scalar() or 0)

    # Top clients across all masters (by spending on completed visits).
    top_result = await db.execute(
        _apply_bounds(
            select(
                ClientProfile.id,
                User.name,
                func.count(Appointment.id).label("visits"),
                func.sum(func.coalesce(Appointment.price, Service.price)).label("spent"),
            )
            .select_from(Appointment)
            .join(ClientProfile, Appointment.client_id == ClientProfile.id)
            .join(User, ClientProfile.user_id == User.id)
            .outerjoin(Service, Appointment.service_id == Service.id)
            .where(Appointment.status == "completed")
            .group_by(ClientProfile.id, User.name)
            .order_by(func.sum(func.coalesce(Appointment.price, Service.price)).desc())
            .limit(5),
            start, end,
        )
    )
    top_clients = [
        {"id": r[0], "name": r[1], "visits": r[2], "spent": float(r[3] or 0)}
        for r in top_result.all()
    ]

    # Recent appointments
    recent_result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.client_profile).joinedload(ClientProfile.user),
            selectinload(Appointment.service),
            selectinload(Appointment.master_profile).joinedload(MasterProfile.user)
        )
        .where(
            Appointment.appointment_date >= localnow_naive(),
            Appointment.status.in_(["pending", "confirmed"]),
        )
        .order_by(Appointment.appointment_date.asc())
        .limit(10)
    )
    recent_appointments = recent_result.scalars().all()

    # Upcoming appointments
    week_from_now = localnow_naive() + timedelta(days=7)
    upcoming_result = await db.execute(
        select(Appointment)
        .options(
            selectinload(Appointment.master_profile).joinedload(MasterProfile.user)
        )
        .where(
            Appointment.appointment_date >= localnow_naive(),
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
        "top_clients": top_clients,
        "recent_appointments": [
            {
                "id": a.id,
                "master_name": a.master_profile.user.name if a.master_profile else None,
                "client_name": a.client_profile.user.name if a.client_profile else None,
                "client_phone": a.client_profile.user.phone if a.client_profile else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status,
                "service_name": a.bundle_name or (a.service.name if a.service else None),
                "service_price": float(a.price) if a.price is not None
                else (float(a.service.price) if a.service else 0)
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

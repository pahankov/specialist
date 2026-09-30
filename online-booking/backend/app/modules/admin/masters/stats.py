"""Master statistics endpoints — get_stats, get_full."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.master_profile import MasterProfile
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.models.review import Review
from app.dependencies.auth import require_super_admin

router = APIRouter()


@router.get("/{master_id}/stats")
async def get_master_stats(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific master (superadmin only)."""
    result = await db.execute(
        select(MasterProfile)
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")

    status_result = await db.execute(
        select(Appointment.status, func.count(Appointment.id))
        .where(Appointment.master_id == master_id)
        .group_by(Appointment.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}

    total_appt = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.master_id == master_id)
    )
    total_appointments = total_appt.scalar() or 0

    client_result = await db.execute(
        select(func.count(ClientProfile.id)).where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == master_id)
            )
        )
    )
    total_clients = client_result.scalar() or 0

    service_result = await db.execute(
        select(func.count(Service.id)).where(Service.master_id == master_id)
    )
    total_services = service_result.scalar() or 0

    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master_id, Appointment.status == "completed")
    )
    total_revenue = float(revenue_result.scalar() or 0)

    recent_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client_profile), selectinload(Appointment.service))
        .where(Appointment.master_id == master_id)
        .order_by(Appointment.appointment_date.desc())
        .limit(5)
    )
    recent_appointments = recent_result.scalars().all()

    return {
        "master_id": master_profile.id,
        "master_name": master_profile.user.name,
        "master_email": master_profile.user.email,
        "is_active": master_profile.is_active,
        "is_admin": master_profile.user.is_admin,
        "total_appointments": total_appointments,
        "status_counts": status_counts,
        "total_clients": total_clients,
        "total_services": total_services,
        "total_revenue": total_revenue,
        "recent_appointments": [
            {
                "id": a.id,
                "client_name": a.client_profile.user.name if a.client_profile else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status,
                "service_name": a.service.name if a.service else None,
                "service_price": float(a.service.price) if a.service else 0
            } for a in recent_appointments
        ]
    }


@router.get("/{master_id}/full")
async def get_master_full(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get complete master profile with stats, rating, reviews, and audit logs."""
    result = await db.execute(
        select(MasterProfile)
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")

    user = master_profile.user

    # --- Appointments stats ---
    status_result = await db.execute(
        select(Appointment.status, func.count(Appointment.id))
        .where(Appointment.master_id == master_id)
        .group_by(Appointment.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}

    total_appt = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.master_id == master_id)
    )
    total_appointments = total_appt.scalar() or 0

    # --- Clients ---
    client_result = await db.execute(
        select(func.count(ClientProfile.id)).where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == master_id)
            )
        )
    )
    total_clients = client_result.scalar() or 0

    # --- Revenue ---
    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master_id, Appointment.status == "completed")
    )
    total_revenue = float(revenue_result.scalar() or 0)

    # --- Average rating ---
    rating_result = await db.execute(
        select(
            func.avg(Review.rating).label("avg_rating"),
            func.count(Review.id).label("count")
        ).where(Review.master_id == master_id, Review.is_published == True)
    )
    row = rating_result.one()
    avg_rating = round(float(row.avg_rating), 1) if row.avg_rating else None
    review_count = row.count

    # --- Recent reviews ---
    reviews_result = await db.execute(
        select(Review)
        .where(Review.master_id == master_id)
        .order_by(Review.created_at.desc())
        .limit(10)
    )
    reviews = reviews_result.scalars().all()
    recent_reviews = [
        {
            "id": r.id,
            "client_name": r.client_name,
            "client_phone": r.client_phone,
            "rating": r.rating,
            "comment": r.comment,
            "is_published": r.is_published,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reviews
    ]

    # --- Recent appointments ---
    recent_appt_result = await db.execute(
        select(Appointment)
        .options(selectinload(Appointment.client_profile), selectinload(Appointment.service))
        .where(Appointment.master_id == master_id)
        .order_by(Appointment.appointment_date.desc())
        .limit(5)
    )
    recent_appts = recent_appt_result.scalars().all()
    recent_appointments = [
        {
            "id": a.id,
            "client_name": a.client_profile.user.name if a.client_profile else None,
            "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
            "status": a.status,
            "service_name": a.service.name if a.service else None,
            "service_price": float(a.service.price) if a.service else 0
        } for a in recent_appts
    ]

    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "avatar_url": master_profile.avatar_url,
        "experience_years": master_profile.experience_years,
        "status": master_profile.status if master_profile.status else "active",
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at.isoformat() if master_profile.created_at else None,
        "updated_at": master_profile.updated_at.isoformat() if master_profile.updated_at else None,
        "stats": {
            "total_appointments": total_appointments,
            "status_counts": status_counts,
            "total_clients": total_clients,
            "total_services": total_services,
            "total_revenue": total_revenue,
            "avg_rating": avg_rating,
            "review_count": review_count,
        },
        "recent_reviews": recent_reviews,
        "recent_appointments": recent_appointments,
    }

"""Superadmin master management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional
from passlib.context import CryptContext
from datetime import datetime, timezone
import csv
import io

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile, MasterStatus
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.service import Service
from app.models.review import Review
from app.schemas.master import MasterCreate, MasterResponse, MasterUpdate
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_admin, require_super_admin
from app.services.audit import log_action
from app.services.master_status import update_master_status_from_working_hours
from app.logging_config import get_logger

logger = get_logger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/masters")


@router.get("", response_model=List[MasterResponse])
async def get_all_masters(
    super_admin: User = Depends(require_super_admin),
    search: Optional[str] = Query(None, description="Search by name or email"),
    filter_active: Optional[str] = Query(None, alias="is_active", description="Filter by active status"),
    filter_admin: Optional[str] = Query(None, alias="is_admin", description="Filter by admin status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all masters (superadmin only)."""
    if search == '':
        search = None
    if filter_active == '':
        filter_active = None
    if filter_admin == '':
        filter_admin = None

    logger.info("GET /admin/masters: search=%r is_active=%r is_admin=%r limit=%d offset=%d",
                search, filter_active, filter_admin, limit, offset)
    
    # Query Users with their MasterProfile using joinedload
    # Show ALL users with MasterProfile (regardless of role)
    query = (
        select(User)
        .join(MasterProfile)
        .options(joinedload(User.master_profile))
    )
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (User.name.ilike(search_term)) | (User.email.ilike(search_term))
        )
    if filter_active is not None:
        active_val = filter_active.lower() in ("true", "1", "yes")
        query = query.where(MasterProfile.is_active == active_val)
    if filter_admin is not None:
        admin_val = filter_admin.lower() in ("true", "1", "yes")
        query = query.where(User.role == UserRole.ADMIN if admin_val else UserRole.MASTER)
    
    query = query.order_by(MasterProfile.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().unique().all()
    
    # Convert User + MasterProfile to response dict
    return [
        {
            "id": u.master_profile.id,
            "user_id": u.id,
            "name": u.name,
            "email": u.email,
            "phone": u.phone,
            "telegram_username": u.master_profile.telegram_username,
            "description": u.master_profile.description,
            "status": u.master_profile.status.value if u.master_profile.status else "active",
            "is_active": u.master_profile.is_active,
            "is_admin": u.is_admin,
            "created_at": u.master_profile.created_at,
            "updated_at": u.master_profile.updated_at,
        }
        for u in users
    ]


@router.get("/{master_id}", response_model=MasterResponse)
async def get_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific master by ID."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    user = master_profile.user
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_master(
    data: MasterCreate,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new master (superadmin only)."""
    # Check if master with this email already exists
    result = await db.execute(select(User).where(User.email == data.email, User.role == UserRole.MASTER))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Мастер с таким email уже существует")
    
    # Check if phone is already in use
    if data.phone:
        result = await db.execute(select(User).where(User.phone == data.phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Мастер с таким телефоном уже существует")
    
    # Create user
    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=pwd_context.hash(data.password),
        phone=data.phone,
        role=UserRole.MASTER,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    
    # Create master profile
    new_master_profile = MasterProfile(user_id=new_user.id)
    db.add(new_master_profile)
    await db.flush()
    await db.refresh(new_master_profile)
    
    await db.commit()
    logger.info("Суперпользователь %s создал мастера: %s", super_admin.email, data.email)
    
    # Return combined response
    return {
        "id": new_master_profile.id,
        "user_id": new_user.id,
        "name": new_user.name,
        "email": new_user.email,
        "phone": new_user.phone,
        "telegram_username": new_master_profile.telegram_username,
        "description": new_master_profile.description,
        "is_active": new_master_profile.is_active,
        "is_admin": new_user.is_admin,
        "created_at": new_master_profile.created_at,
        "updated_at": new_master_profile.updated_at,
    }


@router.patch("/{master_id}", response_model=MasterResponse)
async def update_master(
    master_id: int,
    data: MasterUpdate,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a master (superadmin only)."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    updated_fields = []
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            master_profile.user.hashed_password = pwd_context.hash(value)
            updated_fields.append("password")
        elif field == "name":
            master_profile.user.name = value
            updated_fields.append(field)
        elif field == "email":
            master_profile.user.email = value
            updated_fields.append(field)
        elif field == "phone":
            master_profile.user.phone = value
            updated_fields.append(field)
        elif field == "telegram_username":
            master_profile.telegram_username = value
            updated_fields.append(field)
        else:
            setattr(master_profile, field, value)
            updated_fields.append(field)
    
    await db.commit()
    await db.refresh(master_profile)
    logger.info("Суперпользователь %s обновил мастера %s", super_admin.email, master_profile.user.email)
    
    user = master_profile.user
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.delete("/{master_id}", status_code=200)
async def delete_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a master (superadmin only)."""
    result = await db.execute(select(MasterProfile).where(MasterProfile.id == master_id))
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    # Prevent deleting self
    if master_profile.user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")
    
    await log_action(db, super_admin.master_profile.id if super_admin.master_profile else super_admin.id, "delete", "master", master_id, master_profile.user.email, level="warning")
    await db.delete(master_profile)
    await db.commit()
    logger.info("Суперпользователь %s удалил мастера: %s", super_admin.email, master_profile.user.email)
    return {"detail": "Мастер удалён"}


@router.post("/{master_id}/toggle-active", response_model=MasterResponse)
async def toggle_master_active(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle master active/inactive status (superadmin only)."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    if master_profile.user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать себя")
    
    # Toggle between active and inactive
    if master_profile.status == MasterStatus.ACTIVE:
        master_profile.status = MasterStatus.INACTIVE
        status_str = "отключён"
    else:
        master_profile.status = MasterStatus.ACTIVE
        status_str = "включён"
    
    await db.commit()
    await db.refresh(master_profile)
    logger.info("Суперпользователь %s %s мастера: %s", super_admin.email, status_str, master_profile.user.email)
    
    user = master_profile.user
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "status": master_profile.status.value,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.post("/{master_id}/suspend", response_model=MasterResponse)
async def suspend_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend master (superadmin only). Suspended masters cannot work."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    if master_profile.user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать себя")
    
    master_profile.status = MasterStatus.SUSPENDED
    await db.commit()
    await db.refresh(master_profile)
    logger.info("Суперпользователь %s заблокировал мастера: %s", super_admin.email, master_profile.user.email)
    
    user = master_profile.user
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "status": master_profile.status.value,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.post("/{master_id}/unsuspend", response_model=MasterResponse)
async def unsuspend_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unsuspend master (superadmin only)."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    master_profile.status = MasterStatus.ACTIVE
    await db.commit()
    await db.refresh(master_profile)
    logger.info("Суперпользователь %s разблокировал мастера: %s", super_admin.email, master_profile.user.email)
    
    user = master_profile.user
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "status": master_profile.status.value,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.post("/{master_id}/toggle-admin", response_model=MasterResponse)
async def toggle_master_admin(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle master admin status (superadmin only)."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    if master_profile.user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить свои права")
    
    # Toggle admin role
    if master_profile.user.role == UserRole.ADMIN:
        master_profile.user.role = UserRole.MASTER
        role_str = "лишён прав суперпользователя"
    else:
        master_profile.user.role = UserRole.ADMIN
        role_str = "наделён правами суперпользователя"
    
    await db.commit()
    await db.refresh(master_profile)
    logger.info("Суперпользователь %s %s мастера: %s", super_admin.email, role_str, master_profile.user.email)
    
    user = master_profile.user
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.post("/{master_id}/refresh-status", response_model=MasterResponse)
async def refresh_master_status(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Refresh master status based on working hours (superadmin only)."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    new_status = await update_master_status_from_working_hours(db, master_profile)
    await db.commit()
    await db.refresh(master_profile)
    
    user = master_profile.user
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "status": master_profile.status.value,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.get("/{master_id}/stats")
async def get_master_stats(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific master (superadmin only)."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    # Appointment counts by status
    status_result = await db.execute(
        select(Appointment.status, func.count(Appointment.id))
        .where(Appointment.master_id == master_id)
        .group_by(Appointment.status)
    )
    status_counts = {row[0]: row[1] for row in status_result.all()}
    
    # Total appointments
    total_appt = await db.execute(
        select(func.count(Appointment.id)).where(Appointment.master_id == master_id)
    )
    total_appointments = total_appt.scalar() or 0
    
    # Total clients
    client_result = await db.execute(
        select(func.count(ClientProfile.id)).where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == master_id)
            )
        )
    )
    total_clients = client_result.scalar() or 0
    
    # Total services
    service_result = await db.execute(
        select(func.count(Service.id)).where(Service.master_id == master_id)
    )
    total_services = service_result.scalar() or 0
    
    # Revenue
    revenue_result = await db.execute(
        select(func.sum(Service.price))
        .select_from(Appointment)
        .join(Service, Appointment.service_id == Service.id)
        .where(Appointment.master_id == master_id, Appointment.status == "completed")
    )
    total_revenue = float(revenue_result.scalar() or 0)
    
    # Recent appointments
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
        .options(joinedload(MasterProfile.user))
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
    
    # --- Build response ---
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
        "status": master_profile.status.value if master_profile.status else "active",
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at.isoformat() if master_profile.created_at else None,
        "updated_at": master_profile.updated_at.isoformat() if master_profile.updated_at else None,
        "stats": {
            "total_appointments": total_appointments,
            "status_counts": status_counts,
            "total_clients": total_clients,
            "total_services": total_appt.scalar() or 0,  # placeholder
            "total_revenue": total_revenue,
            "avg_rating": avg_rating,
            "review_count": review_count,
        },
        "recent_reviews": recent_reviews,
        "recent_appointments": recent_appointments,
    }


@router.post("/bulk/toggle-active", response_model=dict)
async def bulk_toggle_active(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle active status for multiple masters at once."""
    results = {"toggled": [], "errors": []}
    
    for mid in master_ids:
        try:
            result = await db.execute(
                select(MasterProfile)
                .options(joinedload(MasterProfile.user))
                .where(MasterProfile.id == mid)
            )
            mp = result.scalar_one_or_none()
            if not mp:
                results["errors"].append({"master_id": mid, "error": "Not found"})
                continue
            if mp.user.id == super_admin.id:
                results["errors"].append({"master_id": mid, "error": "Cannot toggle self"})
                continue
            
            mp.status = MasterStatus.INACTIVE if mp.status == MasterStatus.ACTIVE else MasterStatus.ACTIVE
            results["toggled"].append({
                "master_id": mid,
                "name": mp.user.name,
                "new_status": mp.status.value
            })
        except Exception as e:
            results["errors"].append({"master_id": mid, "error": str(e)})
    
    await db.commit()
    
    for item in results["toggled"]:
        logger.info("Bulk toggle: %s -> %s", item["name"], item["new_status"])
    
    return results


@router.post("/bulk/suspend", response_model=dict)
async def bulk_suspend(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend multiple masters at once."""
    results = {"suspended": [], "errors": []}
    
    for mid in master_ids:
        try:
            result = await db.execute(
                select(MasterProfile)
                .options(joinedload(MasterProfile.user))
                .where(MasterProfile.id == mid)
            )
            mp = result.scalar_one_or_none()
            if not mp:
                results["errors"].append({"master_id": mid, "error": "Not found"})
                continue
            if mp.user.id == super_admin.id:
                results["errors"].append({"master_id": mid, "error": "Cannot suspend self"})
                continue
            
            mp.status = MasterStatus.SUSPENDED
            results["suspended"].append({
                "master_id": mid,
                "name": mp.user.name
            })
        except Exception as e:
            results["errors"].append({"master_id": mid, "error": str(e)})
    
    await db.commit()
    return results


@router.post("/bulk/unsuspend", response_model=dict)
async def bulk_unsuspend(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unsuspend multiple masters at once."""
    results = {"unsuspended": [], "errors": []}
    
    for mid in master_ids:
        try:
            result = await db.execute(
                select(MasterProfile)
                .options(joinedload(MasterProfile.user))
                .where(MasterProfile.id == mid)
            )
            mp = result.scalar_one_or_none()
            if not mp:
                results["errors"].append({"master_id": mid, "error": "Not found"})
                continue
            
            mp.status = MasterStatus.ACTIVE
            results["unsuspended"].append({
                "master_id": mid,
                "name": mp.user.name
            })
        except Exception as e:
            results["errors"].append({"master_id": mid, "error": str(e)})
    
    await db.commit()
    return results


@router.post("/import")
async def import_masters_from_csv(
    file: UploadFile = File(...),
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Import masters from CSV file.
    
    CSV format: name,email,password,phone,telegram_username
    """
    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))
    
    imported = 0
    errors = []
    
    for i, row in enumerate(reader, start=2):  # start=2 because row 1 is header
        try:
            name = row.get("name", "").strip()
            email = row.get("email", "").strip()
            password = row.get("password", "").strip()
            phone = row.get("phone", "").strip() or None
            telegram = row.get("telegram_username", "").strip() or None
            
            if not name or not email or not password:
                errors.append({"row": i, "error": "name, email, password are required"})
                continue
            
            # Check duplicates
            existing = await db.execute(
                select(User).where(User.email == email, User.role == UserRole.MASTER)
            )
            if existing.scalar_one_or_none():
                errors.append({"row": i, "error": f"Email {email} already exists"})
                continue
            
            # Create user
            user = User(
                name=name,
                email=email,
                hashed_password=pwd_context.hash(password),
                phone=phone,
                role=UserRole.MASTER,
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)
            
            # Create master profile
            mp = MasterProfile(
                user_id=user.id,
                telegram_username=telegram,
            )
            db.add(mp)
            imported += 1
            
        except Exception as e:
            errors.append({"row": i, "error": str(e)})
    
    await db.commit()
    
    return {
        "imported": imported,
        "errors": errors,
        "total_rows": imported + len(errors)
    }


@router.get("/audit-logs")
async def get_master_audit_logs(
    master_id: int = Query(None, description="Filter by master ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs, optionally filtered by master_id."""
    from app.models.audit_log import AuditLog
    
    offset = (page - 1) * page_size
    
    base_query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))
    
    if master_id is not None:
        base_query = base_query.where(AuditLog.master_id == master_id)
        count_query = count_query.where(AuditLog.master_id == master_id)
    
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    
    data_query = (
        base_query
        .options(selectinload(AuditLog.master_profile))
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_query)
    logs = result.scalars().all()
    
    items = [
        {
            "id": log.id,
            "master_id": log.master_id,
            "master_name": log.master_profile.user.name if log.master_profile else None,
            "level": log.level,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]
    
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )

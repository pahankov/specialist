"""Superadmin master management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import List, Optional
from passlib.context import CryptContext
from datetime import datetime, timezone

from app.database import get_db
from app.models.master import Master
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.service import Service
from app.schemas.master import MasterCreate, MasterResponse, MasterUpdate
from app.api.dependencies import require_super_admin
from app.api.audit_helper import log_action
from app.logging_config import get_logger

logger = get_logger(__name__)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter(prefix="/masters")


@router.get("", response_model=List[MasterResponse])
async def get_all_masters(
    super_admin: Master = Depends(require_super_admin),
    search: Optional[str] = Query(None, description="Search by name or email"),
    filter_active: Optional[str] = Query(None, alias="is_active", description="Filter by active status"),
    filter_admin: Optional[str] = Query(None, alias="is_admin", description="Filter by admin status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all masters (superadmin only)."""
    logger.info("GET /admin/masters: search=%r is_active=%r is_admin=%r limit=%d offset=%d",
                search, filter_active, filter_admin, limit, offset)
    query = select(Master)
    
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Master.name.ilike(search_term)) | (Master.email.ilike(search_term))
        )
    if filter_active is not None:
        active_val = filter_active.lower() in ("true", "1", "yes")
        query = query.where(Master.is_active == active_val)
    if filter_admin is not None:
        admin_val = filter_admin.lower() in ("true", "1", "yes")
        query = query.where(Master.is_admin == admin_val)
    
    query = query.order_by(Master.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/{master_id}", response_model=MasterResponse)
async def get_master(
    master_id: int,
    super_admin: Master = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific master by ID."""
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    return master


@router.post("", response_model=MasterResponse, status_code=status.HTTP_201_CREATED)
async def create_master(
    data: MasterCreate,
    super_admin: Master = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new master (superadmin only)."""
    result = await db.execute(select(Master).where(Master.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Мастер с таким email уже существует")
    
    new_master = Master(
        name=data.name,
        email=data.email,
        hashed_password=pwd_context.hash(data.password),
        phone=data.phone,
        telegram_username=data.telegram_username,
    )
    db.add(new_master)
    await log_action(db, super_admin.id, "create", "master", new_master.id, data.email, level="info")
    await db.commit()
    await db.refresh(new_master)
    logger.info("Суперпользователь %s создал мастера: %s", super_admin.email, data.email)
    return new_master


@router.patch("/{master_id}", response_model=MasterResponse)
async def update_master(
    master_id: int,
    data: MasterUpdate,
    super_admin: Master = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Update a master (superadmin only)."""
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    updated_fields = []
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            master.hashed_password = pwd_context.hash(value)
            updated_fields.append("password")
        else:
            setattr(master, field, value)
            updated_fields.append(field)
    
    await log_action(db, super_admin.id, "update", "master", master_id, 
                     f"Обновлены поля: {', '.join(updated_fields)}", level="info")
    await db.commit()
    await db.refresh(master)
    logger.info("Суперпользователь %s обновил мастера %s", super_admin.email, master.email)
    return master


@router.delete("/{master_id}", status_code=200)
async def delete_master(
    master_id: int,
    super_admin: Master = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a master (superadmin only)."""
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    # Prevent deleting self
    if master.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")
    
    await log_action(db, super_admin.id, "delete", "master", master_id, master.email, level="warning")
    await db.delete(master)
    await db.commit()
    logger.info("Суперпользователь %s удалил мастера: %s", super_admin.email, master.email)
    return {"detail": "Мастер удалён"}


@router.post("/{master_id}/toggle-active", response_model=MasterResponse)
async def toggle_master_active(
    master_id: int,
    super_admin: Master = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle master active/inactive status (superadmin only)."""
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    if master.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать себя")
    
    master.is_active = not master.is_active
    status_str = "заблокирован" if not master.is_active else "разблокирован"
    await log_action(db, super_admin.id, "toggle_active", "master", master_id, 
                     f"Мастер {status_str}", level="warning")
    await db.commit()
    await db.refresh(master)
    logger.info("Суперпользователь %s %s мастера: %s", super_admin.email, status_str, master.email)
    return master


@router.post("/{master_id}/toggle-admin", response_model=MasterResponse)
async def toggle_master_admin(
    master_id: int,
    super_admin: Master = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle master admin status (superadmin only)."""
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    
    if master.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить свои права")
    
    master.is_admin = not master.is_admin
    role_str = "наделён правами суперпользователя" if master.is_admin else "лишён прав суперпользователя"
    await log_action(db, super_admin.id, "toggle_admin", "master", master_id, 
                     f"Мастер {role_str}", level="warning")
    await db.commit()
    await db.refresh(master)
    logger.info("Суперпользователь %s %s мастера: %s", super_admin.email, role_str, master.email)
    return master


@router.get("/{master_id}/stats")
async def get_master_stats(
    master_id: int,
    super_admin: Master = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get statistics for a specific master (superadmin only)."""
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
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
        select(func.count(Client.id)).where(
            Client.id.in_(
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
        .options(selectinload(Appointment.client), selectinload(Appointment.service))
        .where(Appointment.master_id == master_id)
        .order_by(Appointment.appointment_date.desc())
        .limit(5)
    )
    recent_appointments = recent_result.scalars().all()
    
    return {
        "master_id": master.id,
        "master_name": master.name,
        "master_email": master.email,
        "is_active": master.is_active,
        "is_admin": master.is_admin,
        "total_appointments": total_appointments,
        "status_counts": status_counts,
        "total_clients": total_clients,
        "total_services": total_services,
        "total_revenue": total_revenue,
        "recent_appointments": [
            {
                "id": a.id,
                "client_name": a.client.name if a.client else None,
                "appointment_date": a.appointment_date.isoformat() if a.appointment_date else None,
                "status": a.status,
                "service_name": a.service.name if a.service else None,
                "service_price": float(a.service.price) if a.service else 0
            } for a in recent_appointments
        ]
    }

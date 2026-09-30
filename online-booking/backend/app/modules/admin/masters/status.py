"""Master status management — toggle, suspend, unsuspend, admin role."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.schemas.master import MasterResponse
from app.dependencies.auth import require_super_admin
from app.services.master_status import update_master_status_from_working_hours
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _to_response(user: User, master_profile: MasterProfile) -> dict:
    """Convert User + MasterProfile to response dict."""
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "status": master_profile.status,
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


async def _get_master_or_404(db, master_id: int):
    """Load MasterProfile with User or raise 404."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    return mp


@router.post("/{master_id}/toggle-active", response_model=MasterResponse)
async def toggle_master_active(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle master active/inactive status (superadmin only)."""
    mp = await _get_master_or_404(db, master_id)

    if mp.user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать себя")

    if mp.status == "active":
        mp.status = "inactive"
        status_str = "отключён"
    else:
        mp.status = "active"
        status_str = "включён"

    await db.commit()
    await db.refresh(mp)
    logger.info("Суперпользователь %s %s мастера: %s", super_admin.email, status_str, mp.user.email)

    return _to_response(mp.user, mp)


@router.post("/{master_id}/suspend", response_model=MasterResponse)
async def suspend_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend master (superadmin only)."""
    mp = await _get_master_or_404(db, master_id)

    if mp.user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать себя")

    mp.status = "suspended"
    await db.commit()
    await db.refresh(mp)
    logger.info("Суперпользователь %s заблокировал мастера: %s", super_admin.email, mp.user.email)

    return _to_response(mp.user, mp)


@router.post("/{master_id}/unsuspend", response_model=MasterResponse)
async def unsuspend_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unsuspend master (superadmin only)."""
    mp = await _get_master_or_404(db, master_id)

    mp.status = "active"
    await db.commit()
    await db.refresh(mp)
    logger.info("Суперпользователь %s разблокировал мастера: %s", super_admin.email, mp.user.email)

    return _to_response(mp.user, mp)


@router.post("/{master_id}/toggle-admin", response_model=MasterResponse)
async def toggle_master_admin(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle master admin status (superadmin only)."""
    mp = await _get_master_or_404(db, master_id)

    if mp.user.id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя изменить свои права")

    if mp.user.role == UserRole.ADMIN:
        mp.user.role = UserRole.MASTER
        role_str = "лишён прав суперпользователя"
    else:
        mp.user.role = UserRole.ADMIN
        role_str = "наделён правами суперпользователя"

    await db.commit()
    await db.refresh(mp)
    logger.info("Суперпользователь %s %s мастера: %s", super_admin.email, role_str, mp.user.email)

    # Return response without status field for toggle-admin
    return {
        "id": mp.id,
        "user_id": mp.user.id,
        "name": mp.user.name,
        "email": mp.user.email,
        "phone": mp.user.phone,
        "telegram_username": mp.telegram_username,
        "description": mp.description,
        "is_active": mp.is_active,
        "is_admin": mp.user.is_admin,
        "created_at": mp.created_at,
        "updated_at": mp.updated_at,
    }


@router.post("/{master_id}/refresh-status", response_model=MasterResponse)
async def refresh_master_status(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Refresh master status based on working hours (superadmin only)."""
    mp = await _get_master_or_404(db, master_id)

    await update_master_status_from_working_hours(db, mp)
    await db.commit()
    await db.refresh(mp)

    return _to_response(mp.user, mp)

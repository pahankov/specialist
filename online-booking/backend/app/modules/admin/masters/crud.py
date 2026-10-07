"""Master CRUD endpoints — create, read, update, delete."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.schemas.master import MasterCreate, MasterResponse, MasterUpdate
from app.dependencies.auth import require_super_admin
from app.utils.security import hash_password
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/masters", tags=["masters"])


def _to_response(user: User, master_profile: MasterProfile) -> dict:
    """Convert User + MasterProfile to response dict."""
    return {
        "id": master_profile.id,
        "user_id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "telegram_username": master_profile.telegram_username,
        "description": master_profile.description,
        "status": master_profile.status if master_profile.status else "active",
        "is_active": master_profile.is_active,
        "is_admin": user.is_admin,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


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

    return [_to_response(u, u.master_profile) for u in users]


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

    return _to_response(master_profile.user, master_profile)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_master(
    data: MasterCreate,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Create a new master (superadmin only)."""
    result = await db.execute(select(User).where(User.email == data.email, User.role == UserRole.MASTER))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Мастер с таким email уже существует")

    if data.phone:
        result = await db.execute(select(User).where(User.phone == data.phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Мастер с таким телефоном уже существует")

    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        phone=data.phone,
        role=UserRole.MASTER,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    new_master_profile = MasterProfile(user_id=new_user.id)
    db.add(new_master_profile)
    await db.flush()
    await db.refresh(new_master_profile)

    await db.commit()
    logger.info("Суперпользователь %s создал мастера: %s", super_admin.email, data.email)

    return _to_response(new_user, new_master_profile)


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

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            master_profile.user.hashed_password = hash_password(value)
        elif field == "name":
            master_profile.user.name = value
        elif field == "email":
            master_profile.user.email = value
        elif field == "phone":
            master_profile.user.phone = value
        elif field == "telegram_username":
            master_profile.telegram_username = value
        else:
            setattr(master_profile, field, value)

    await db.commit()
    await db.refresh(master_profile)
    logger.info("Суперпользователь %s обновил мастера %s", super_admin.email, master_profile.user.email)

    return _to_response(master_profile.user, master_profile)


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

    if master_profile.user_id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")

    await db.delete(master_profile)
    await db.commit()
    logger.info("Суперпользователь %s удалил мастера (user_id=%s)", super_admin.email, master_profile.user_id)
    return {"detail": "Мастер удалён"}

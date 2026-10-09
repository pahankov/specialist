"""Master CRUD endpoints — create, read, update, delete."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Optional

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.city import City
from app.schemas.master import MasterCreate, MasterResponse, MasterUpdate
from app.dependencies.auth import require_super_admin
from app.utils.security import hash_password
from app.services.audit import log_action
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
        "tariff": master_profile.tariff or "trial",
        "trial_ends_at": master_profile.trial_ends_at,
        "created_at": master_profile.created_at,
        "updated_at": master_profile.updated_at,
    }


@router.get("", response_model=List[MasterResponse])
async def get_all_masters(
    super_admin: User = Depends(require_super_admin),
    search: Optional[str] = Query(None, description="Search by name or email"),
    filter_active: Optional[str] = Query(None, alias="is_active", description="Filter by active status"),
    filter_admin: Optional[str] = Query(None, alias="is_admin", description="Filter by admin status"),
    sort_by: Optional[str] = Query(None, description="Sort column: name|email|status|created_at"),
    sort_dir: str = Query("asc", description="Sort direction: asc|desc"),
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

    if sort_by:
        sort_col = _SORTABLE_MASTERS.get(sort_by, MasterProfile.created_at)
        query = query.order_by(
            sort_col.desc() if str(sort_dir).lower() == "desc" else sort_col.asc()
        )
    else:
        # Preserve legacy default: newest first
        query = query.order_by(MasterProfile.created_at.desc())
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    users = result.scalars().unique().all()

    return [_to_response(u, u.master_profile) for u in users]


_SORTABLE_MASTERS = {
    "name": User.name,
    "email": User.email,
    "status": MasterProfile.status,
    "created_at": MasterProfile.created_at,
}


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
        logger.warning("Создание мастера отклонено %s: email %s уже существует", super_admin.email, data.email)
        raise HTTPException(status_code=400, detail="Мастер с таким email уже существует")

    if data.phone:
        result = await db.execute(select(User).where(User.phone == data.phone))
        if result.scalar_one_or_none():
            logger.warning("Создание мастера отклонено %s: телефон %s уже существует", super_admin.email, data.phone)
            raise HTTPException(status_code=400, detail="Мастер с таким телефоном уже существует")

    if data.city_id is not None:
        city = await db.execute(select(City).where(City.id == data.city_id))
        if city.scalar_one_or_none() is None:
            logger.warning("Создание мастера отклонено %s: город id=%s не найден", super_admin.email, data.city_id)
            raise HTTPException(status_code=400, detail="Город не найден")

    new_user = User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
        phone=data.phone,
        role=UserRole.MASTER,
        city_id=data.city_id,
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
    await log_action(db, super_admin.id, "create", "master", new_user.id, data.name, level="info")
    await db.commit()

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

    fields = data.model_dump(exclude_unset=True)
    # Unique phone/email must not collide with OTHER users: without this
    # check prod seed duplicates turn the save into a 500 (IntegrityError).
    if "phone" in fields and fields["phone"]:
        dup = await db.execute(
            select(User.id).where(User.phone == fields["phone"], User.id != master_profile.user_id)
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Мастер с таким телефоном уже существует")
    if "email" in fields and fields["email"]:
        dup = await db.execute(
            select(User.id).where(User.email == fields["email"], User.id != master_profile.user_id)
        )
        if dup.scalar_one_or_none() is not None:
            raise HTTPException(status_code=400, detail="Мастер с таким email уже существует")

    for field, value in fields.items():
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

    from sqlalchemy.exc import IntegrityError
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        logger.warning("Обновление мастера %s отклонено: конфликт уникальности", master_id)
        raise HTTPException(status_code=400, detail="Такие телефон или email уже заняты другим пользователем")
    await db.refresh(master_profile)
    logger.info("Суперпользователь %s обновил мастера %s", super_admin.email, master_profile.user.email)
    await log_action(db, super_admin.id, "update", "master", master_profile.user_id,
                     f"Обновлён мастер {master_profile.user.email}", level="info")
    await db.commit()

    return _to_response(master_profile.user, master_profile)


@router.delete("/{master_id}", status_code=200)
async def delete_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Delete a master with ALL their data (superadmin only).

    Children are removed explicitly in FK order instead of relying on
    DB-level ON DELETE CASCADE: prod constraints predating the models
    may lack it, which turned deletes into 500s.
    """
    from app.models.appointment import Appointment
    from app.models.blocked_slot import BlockedSlot
    from app.models.refresh_token import RefreshToken
    from app.models.review import Review
    from app.models.service import Service
    from app.models.working_hour import WorkingHour
    from sqlalchemy import delete as sa_delete

    result = await db.execute(select(MasterProfile).where(MasterProfile.id == master_id))
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")

    if master_profile.user_id == super_admin.id:
        raise HTTPException(status_code=400, detail="Нельзя удалить себя")

    user_result = await db.execute(select(User).where(User.id == master_profile.user_id))
    user = user_result.scalar_one_or_none()
    user_name = user.name if user else f"user_id={master_profile.user_id}"
    user_id = master_profile.user_id

    await db.execute(sa_delete(Appointment).where(Appointment.master_id == master_id))
    await db.execute(sa_delete(Service).where(Service.master_id == master_id))
    await db.execute(sa_delete(WorkingHour).where(WorkingHour.master_id == master_id))
    await db.execute(sa_delete(BlockedSlot).where(BlockedSlot.master_id == master_id))
    await db.execute(sa_delete(Review).where(Review.master_id == master_id))
    await db.execute(sa_delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.delete(master_profile)
    if user is not None:
        await db.delete(user)
    await log_action(db, super_admin.id, "delete", "master", user_id,
                     f"Удалён мастер {user_name} вместе со всеми данными", level="warning")
    await db.commit()
    logger.info("Суперпользователь %s удалил мастера %s", super_admin.email, user_name)
    return {"detail": "Мастер удалён"}

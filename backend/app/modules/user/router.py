"""User module — master and client CRUD endpoints (updated for unified user model)."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from typing import List
from pydantic import BaseModel
from passlib.context import CryptContext

from app.database import get_db
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.models.client_profile import ClientProfile
from app.schemas.master import MasterCreate, MasterUpdate
from app.schemas.client import ClientCreate
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ─── Masters ──────────────────────────────────────────────────────────

@router.get("/masters/", response_model=List[dict])
async def get_masters(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(MasterProfile)
        .join(MasterProfile.user)
        .options(joinedload(MasterProfile.user))
        .where(User.role == UserRole.MASTER)  # exclude superadmins
        .order_by(User.name)
        .offset(offset).limit(limit)
    )
    profiles = result.scalars().all()
    return [_master_profile_to_dict(mp) for mp in profiles]


@router.get("/masters/{master_id}", response_model=dict)
async def get_master(master_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(MasterProfile)
        .where(MasterProfile.id == master_id)
        .options(joinedload(MasterProfile.user))
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=404, detail="Master not found")
    return _master_profile_to_dict(mp)


@router.post("/masters/", response_model=dict, status_code=201)
async def create_master(
    master: MasterCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == master.email, User.role == UserRole.MASTER))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Master with this email already exists")

    new_user = User(
        name=master.name,
        email=master.email,
        hashed_password=pwd_context.hash(master.password),
        phone=master.phone,
        role=UserRole.MASTER,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    new_mp = MasterProfile(user_id=new_user.id)
    db.add(new_mp)
    await db.flush()
    await db.refresh(new_mp)
    return _master_profile_to_dict(new_mp)


@router.patch("/masters/{master_id}", response_model=dict)
async def update_master(
    master_id: int,
    master_update: MasterUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(MasterProfile)
        .where(MasterProfile.id == master_id)
        .options(joinedload(MasterProfile.user))
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=404, detail="Master not found")

    for field, value in master_update.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            mp.user.hashed_password = pwd_context.hash(value)
        elif field == "name":
            mp.user.name = value
        elif field == "phone":
            mp.user.phone = value
        elif field == "telegram_username":
            mp.telegram_username = value
        else:
            setattr(mp, field, value)

    await db.commit()
    await db.refresh(mp)
    return _master_profile_to_dict(mp)


@router.delete("/masters/{master_id}", status_code=200)
async def delete_master(master_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("Удаление мастера: id=%s", master_id)
    result = await db.execute(
        select(MasterProfile)
        .where(MasterProfile.id == master_id)
        .options(joinedload(MasterProfile.user))
    )
    mp = result.scalar_one_or_none()
    if not mp:
        logger.warning("Мастер не найден для удаления: id=%s", master_id)
        raise HTTPException(status_code=404, detail="Master not found")

    await db.delete(mp)
    await db.commit()
    logger.info("Мастер успешно удалён: id=%s", master_id)
    return {"detail": "Master deleted"}


# ─── Clients ──────────────────────────────────────────────────────────

@router.get("/clients/", response_model=List[dict])
async def get_clients(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(ClientProfile)
        .join(ClientProfile.user)
        .options(joinedload(ClientProfile.user))
        .order_by(User.name)
        .offset(offset).limit(limit)
    )
    profiles = result.scalars().all()
    return [_client_profile_to_dict(cp) for cp in profiles]


@router.get("/clients/{client_id}", response_model=dict)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ClientProfile)
        .where(ClientProfile.id == client_id)
        .options(joinedload(ClientProfile.user))
    )
    cp = result.scalar_one_or_none()
    if not cp:
        raise HTTPException(status_code=404, detail="Client not found")
    return _client_profile_to_dict(cp)


@router.post("/clients/", response_model=dict, status_code=201)
async def create_client(
    client: ClientCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.phone == client.phone, User.role == UserRole.CLIENT))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Client with this phone already exists")

    new_user = User(
        name=client.name,
        phone=client.phone,
        email=client.email,
        role=UserRole.CLIENT,
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)

    new_cp = ClientProfile(user_id=new_user.id)
    db.add(new_cp)
    await db.flush()
    await db.refresh(new_cp)
    return _client_profile_to_dict(new_cp)


@router.delete("/clients/{client_id}", status_code=204)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("Удаление клиента: id=%s", client_id)
    result = await db.execute(
        select(ClientProfile)
        .where(ClientProfile.id == client_id)
        .options(joinedload(ClientProfile.user))
    )
    cp = result.scalar_one_or_none()
    if not cp:
        logger.warning("Клиент не найден для удаления: id=%s", client_id)
        raise HTTPException(status_code=404, detail="Client not found")
    await db.delete(cp)
    await db.commit()
    logger.info("Клиент успешно удалён: id=%s", client_id)
    return None


# ─── Helpers ──────────────────────────────────────────────────────────

def _master_profile_to_dict(mp):
    return {
        "id": mp.id,
        "user_id": mp.user_id,
        "name": mp.user.name,
        "email": mp.user.email,
        "phone": mp.user.phone,
        "telegram_username": mp.telegram_username,
        "description": mp.description,
        "avatar_url": mp.avatar_url,
        "is_active": mp.is_active,
        "is_admin": mp.user.is_admin,
        "created_at": mp.created_at.isoformat() if mp.created_at else None,
        "updated_at": mp.updated_at.isoformat() if mp.updated_at else None,
    }


def _client_profile_to_dict(cp):
    return {
        "id": cp.id,
        "user_id": cp.user_id,
        "name": cp.user.name,
        "phone": cp.user.phone,
        "email": cp.user.email,
        "no_show_count": cp.no_show_count,
        "created_at": cp.created_at.isoformat() if cp.created_at else None,
        "updated_at": cp.updated_at.isoformat() if cp.updated_at else None,
    }

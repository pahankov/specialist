"""User module — master and client CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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
        select(MasterProfile).join(MasterProfile.user).where(User.role == UserRole.MASTER)
        .offset(offset).limit(limit)
    )
    master_profiles = result.scalars().all()
    return [_master_profile_to_dict(m) for m in master_profiles]


@router.get("/masters/{master_id}", response_model=dict)
async def get_master(master_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MasterProfile).where(MasterProfile.id == master_id))
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Master not found")
    return _master_profile_to_dict(master_profile)


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
    
    new_master_profile = MasterProfile(user_id=new_user.id)
    db.add(new_master_profile)
    await db.flush()
    await db.refresh(new_master_profile)
    return _master_profile_to_dict(new_master_profile)


@router.patch("/masters/{master_id}", response_model=dict)
async def update_master(
    master_id: int,
    master_update: MasterUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(MasterProfile).where(MasterProfile.id == master_id))
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        raise HTTPException(status_code=404, detail="Master not found")

    for field, value in master_update.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            master_profile.user.hashed_password = pwd_context.hash(value)
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
    return _master_profile_to_dict(master_profile)


@router.delete("/masters/{master_id}", status_code=200)
async def delete_master(master_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("Удаление мастера: id=%s", master_id)
    result = await db.execute(select(MasterProfile).where(MasterProfile.id == master_id))
    master_profile = result.scalar_one_or_none()
    if not master_profile:
        logger.warning("Мастер не найден для удаления: id=%s", master_id)
        raise HTTPException(status_code=404, detail="Master not found")

    await db.delete(master_profile)
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
        select(ClientProfile).join(ClientProfile.user).where(User.role == UserRole.CLIENT)
        .offset(offset).limit(limit)
    )
    client_profiles = result.scalars().all()
    return [_client_profile_to_dict(c) for c in client_profiles]


@router.get("/clients/{client_id}", response_model=dict)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ClientProfile).where(ClientProfile.id == client_id))
    client_profile = result.scalar_one_or_none()
    if not client_profile:
        raise HTTPException(status_code=404, detail="Client not found")
    return _client_profile_to_dict(client_profile)


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
        role=UserRole.CLIENT
    )
    db.add(new_user)
    await db.flush()
    await db.refresh(new_user)
    
    new_client_profile = ClientProfile(user_id=new_user.id)
    db.add(new_client_profile)
    await db.flush()
    await db.refresh(new_client_profile)
    return _client_profile_to_dict(new_client_profile)


@router.delete("/clients/{client_id}", status_code=204)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("Удаление клиента: id=%s", client_id)
    result = await db.execute(select(ClientProfile).where(ClientProfile.id == client_id))
    client_profile = result.scalar_one_or_none()
    if not client_profile:
        logger.warning("Клиент не найден для удаления: id=%s", client_id)
        raise HTTPException(status_code=404, detail="Client not found")
    await db.delete(client_profile)
    await db.commit()
    logger.info("Клиент успешно удалён: id=%s", client_id)
    return None


# ─── Helpers ──────────────────────────────────────────────────────────

def _master_profile_to_dict(m):
    return {
        "id": m.id,
        "user_id": m.user_id,
        "name": m.user.name,
        "email": m.user.email,
        "phone": m.user.phone,
        "telegram_username": m.telegram_username,
        "description": m.description,
        "avatar_url": m.avatar_url,
        "is_active": m.is_active,
        "is_admin": m.user.is_admin,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _client_profile_to_dict(c):
    return {
        "id": c.id,
        "user_id": c.user_id,
        "name": c.user.name,
        "phone": c.user.phone,
        "email": c.user.email,
        "no_show_count": c.no_show_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }

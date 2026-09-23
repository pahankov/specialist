"""User module — master and client CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from pydantic import BaseModel
from passlib.context import CryptContext

from app.database import get_db
from app.models.master import Master
from app.models.client import Client
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
        select(Master).offset(offset).limit(limit)
    )
    masters = result.scalars().all()
    return [_master_to_dict(m) for m in masters]


@router.get("/masters/{master_id}", response_model=dict)
async def get_master(master_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Master not found")
    return _master_to_dict(master)


@router.post("/masters/", response_model=dict, status_code=201)
async def create_master(
    master: MasterCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Master).where(Master.email == master.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Master with this email already exists")

    new_master = Master(
        name=master.name,
        email=master.email,
        hashed_password=pwd_context.hash(master.password),
        phone=master.phone,
        telegram_username=master.telegram_username
    )
    db.add(new_master)
    await db.commit()
    await db.refresh(new_master)
    return _master_to_dict(new_master)


@router.patch("/masters/{master_id}", response_model=dict)
async def update_master(
    master_id: int,
    master_update: MasterUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Master not found")

    for field, value in master_update.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            master.hashed_password = pwd_context.hash(value)
        else:
            setattr(master, field, value)

    await db.commit()
    await db.refresh(master)
    return _master_to_dict(master)


@router.delete("/masters/{master_id}", status_code=200)
async def delete_master(master_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("Удаление мастера: id=%s", master_id)
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        logger.warning("Мастер не найден для удаления: id=%s", master_id)
        raise HTTPException(status_code=404, detail="Master not found")

    await db.delete(master)
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
        select(Client).offset(offset).limit(limit)
    )
    clients = result.scalars().all()
    return [_client_to_dict(c) for c in clients]


@router.get("/clients/{client_id}", response_model=dict)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return _client_to_dict(client)


@router.post("/clients/", response_model=dict, status_code=201)
async def create_client(
    client: ClientCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Client).where(Client.phone == client.phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Client with this phone already exists")

    new_client = Client(**client.model_dump())
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    return _client_to_dict(new_client)


@router.delete("/clients/{client_id}", status_code=204)
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("Удаление клиента: id=%s", client_id)
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        logger.warning("Клиент не найден для удаления: id=%s", client_id)
        raise HTTPException(status_code=404, detail="Client not found")
    await db.delete(client)
    await db.commit()
    logger.info("Клиент успешно удалён: id=%s", client_id)
    return None


# ─── Helpers ──────────────────────────────────────────────────────────

def _master_to_dict(m):
    return {
        "id": m.id,
        "name": m.name,
        "email": m.email,
        "phone": m.phone,
        "telegram_username": m.telegram_username,
        "description": m.description,
        "avatar_url": m.avatar_url,
        "is_active": m.is_active,
        "is_admin": m.is_admin,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _client_to_dict(c):
    return {
        "id": c.id,
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "no_show_count": c.no_show_count,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }

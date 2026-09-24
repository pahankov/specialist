"""Admin client CRUD endpoints."""
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List, Optional

from app.database import get_db
from app.models.client_profile import ClientProfile
from app.models.user import User
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.dependencies.auth import require_master
from app.dependencies.crud import get_or_404
from app.services.audit import log_action

router = APIRouter()


@router.get("/clients", response_model=List[ClientResponse])
async def get_admin_clients(
    master: User = Depends(require_master),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all clients (paginated)."""
    result = await db.execute(
        select(ClientProfile)
        .join(ClientProfile.user)
        .options(joinedload(ClientProfile.user))
        .order_by(User.name)
        .offset(offset)
        .limit(limit)
    )
    profiles = result.scalars().unique().all()
    # Return user data wrapped in ClientResponse format
    return [
        {
            "id": cp.user.id,
            "name": cp.user.name,
            "phone": cp.user.phone,
            "email": cp.user.email,
            "no_show_count": cp.no_show_count,
            "created_at": cp.user.created_at.isoformat() if cp.user.created_at else None,
            "updated_at": cp.user.updated_at.isoformat() if cp.user.updated_at else None,
        }
        for cp in profiles
    ]


@router.post("/clients", response_model=ClientResponse, status_code=201)
async def create_admin_client(
    data: ClientCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new client with duplicate check."""
    result = await db.execute(select(User).where(User.phone == data.phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")
    if data.email:
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")
    
    user = User(name=data.name, phone=data.phone, email=data.email, role="CLIENT")
    db.add(user)
    await db.flush()
    
    client_profile = ClientProfile(user_id=user.id)
    db.add(client_profile)
    await db.flush()
    await db.refresh(user)
    
    await log_action(db, master.id, "create", "client", user.id, data.name, level="info")
    await db.commit()
    
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "no_show_count": 0,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.patch("/clients/{client_id}", response_model=ClientResponse)
async def update_admin_client(
    client_id: int,
    data: ClientUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update a client with duplicate check."""
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    
    if data.phone and data.phone != user.phone:
        result = await db.execute(select(User).where(User.phone == data.phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")
    if data.email and data.email != (user.email or ''):
        result = await db.execute(select(User).where(User.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")
    
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    
    await log_action(db, master.id, "update", "client", client_id, f"Обновлены поля: {', '.join(data.model_dump(exclude_unset=True).keys())}", level="info")
    await db.commit()
    await db.refresh(user)
    
    return {
        "id": user.id,
        "name": user.name,
        "phone": user.phone,
        "email": user.email,
        "no_show_count": 0,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.delete("/clients/{client_id}", status_code=204)
async def delete_admin_client(
    client_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete a client."""
    result = await db.execute(select(User).where(User.id == client_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Client not found")
    
    await log_action(db, master.id, "delete", "client", client_id, user.name, level="warning")
    await db.delete(user)
    await db.commit()
    return None

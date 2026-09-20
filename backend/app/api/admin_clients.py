"""Admin client CRUD endpoints."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from fastapi import HTTPException
from app.api.admin_base import (
    get_db, Appointment, Client, Master, require_master, get_or_404, log_action,
    ClientCreate, ClientUpdate, ClientResponse
)

router = APIRouter()


@router.get("/clients", response_model=List[ClientResponse])
async def get_admin_clients(
    master: Master = Depends(require_master),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all clients (paginated)."""
    result = await db.execute(select(Client).order_by(Client.name).offset(offset).limit(limit))
    return result.scalars().all()


@router.post("/clients", response_model=ClientResponse, status_code=201)
async def create_admin_client(
    data: ClientCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a new client with duplicate check."""
    result = await db.execute(select(Client).where(Client.phone == data.phone))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")
    if data.email:
        result = await db.execute(select(Client).where(Client.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")
    new_client = Client(name=data.name, phone=data.phone, email=data.email)
    db.add(new_client)
    await log_action(db, master.id, "create", "client", new_client.id, data.name, level="info")
    await db.commit()
    await db.refresh(new_client)
    return new_client


@router.patch("/clients/{client_id}", response_model=ClientResponse)
async def update_admin_client(
    client_id: int,
    data: ClientUpdate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update a client with duplicate check."""
    client = await get_or_404(db, Client, client_id)
    if data.phone and data.phone != client.phone:
        result = await db.execute(select(Client).where(Client.phone == data.phone))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким телефоном уже существует")
    if data.email and data.email != (client.email or ''):
        result = await db.execute(select(Client).where(Client.email == data.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Клиент с таким email уже существует")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    await log_action(db, master.id, "update", "client", client_id, f"Обновлены поля: {', '.join(data.model_dump(exclude_unset=True).keys())}", level="info")
    await db.commit()
    await db.refresh(client)
    return client


@router.delete("/clients/{client_id}", status_code=204)
async def delete_admin_client(
    client_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete a client."""
    client = await get_or_404(db, Client, client_id)
    await log_action(db, master.id, "delete", "client", client_id, client.name, level="warning")
    await db.delete(client)
    await db.commit()
    return None

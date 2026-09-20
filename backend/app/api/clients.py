from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.database import get_db
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientResponse
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/", response_model=List[ClientResponse])
async def get_clients(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(Client).offset(offset).limit(limit)
    )
    return result.scalars().all()

@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(client_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client

@router.post("/", response_model=ClientResponse, status_code=201)
async def create_client(client: ClientCreate, db: AsyncSession = Depends(get_db)):
    # Check if client already exists
    result = await db.execute(select(Client).where(Client.phone == client.phone))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Client with this phone already exists")
    
    new_client = Client(**client.model_dump())
    db.add(new_client)
    await db.commit()
    await db.refresh(new_client)
    return new_client

@router.delete("/{client_id}", status_code=204)
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
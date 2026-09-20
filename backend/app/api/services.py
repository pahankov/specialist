from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.database import get_db
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceResponse
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

@router.get("/", response_model=List[ServiceResponse])
async def get_services(
    db: AsyncSession = Depends(get_db),
    master_id: int = Query(None),
    is_active: bool = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    query = select(Service)
    if master_id is not None:
        query = query.where(Service.master_id == master_id)
    if is_active is not None:
        query = query.where(Service.is_active == is_active)
    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{service_id}", response_model=ServiceResponse)
async def get_service(service_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service

@router.post("/", response_model=ServiceResponse, status_code=201)
async def create_service(service: ServiceCreate, db: AsyncSession = Depends(get_db)):
    if service.master_id is None:
        raise HTTPException(status_code=422, detail="master_id is required")
    new_service = Service(
        master_id=service.master_id,
        name=service.name,
        description=service.description,
        duration_minutes=service.duration_minutes,
        price=service.price,
        is_active=True
    )
    db.add(new_service)
    await db.commit()
    await db.refresh(new_service)
    return new_service

@router.delete("/{service_id}", status_code=204)
async def delete_service(service_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Service).where(Service.id == service_id))
    service = result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    await db.delete(service)
    await db.commit()
    return None
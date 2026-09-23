"""Admin service CRUD endpoints."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.modules.admin.base import (
    get_db, Service, User, require_master, get_owned_or_404, log_action,
    ServiceCreate, ServiceResponse, ServiceUpdate
)

router = APIRouter()


@router.post("/services", response_model=ServiceResponse, status_code=201)
async def create_admin_service(
    data: ServiceCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create a service for the authenticated master."""
    new_service = Service(
        master_id=master.master_profile.id, name=data.name, description=data.description,
        duration_minutes=data.duration_minutes, price=data.price, is_active=True
    )
    db.add(new_service)
    await db.flush()
    await db.refresh(new_service)
    await log_action(db, master.master_profile.id, "create", "service", new_service.id, data.name, level="info")
    await db.commit()
    return new_service


@router.get("/services", response_model=List[ServiceResponse])
async def get_admin_services(
    master: User = Depends(require_master),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get active services (paginated)."""
    result = await db.execute(
        select(Service).where(Service.master_id == master.master_profile.id, Service.is_active == True)
        .order_by(Service.name).offset(offset).limit(limit)
    )
    return result.scalars().all()


@router.get("/services/all", response_model=List[ServiceResponse])
async def get_all_admin_services(
    master: User = Depends(require_master),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get all services including inactive (paginated)."""
    result = await db.execute(
        select(Service).where(Service.master_id == master.master_profile.id)
        .order_by(Service.name).offset(offset).limit(limit)
    )
    return result.scalars().all()


@router.patch("/services/{service_id}", response_model=ServiceResponse)
async def update_admin_service(
    service_id: int,
    data: ServiceUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update a service."""
    service = await get_owned_or_404(db, Service, service_id, master.master_profile.id)
    changes = []
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
        changes.append(field)
    await log_action(db, master.master_profile.id, "update", "service", service_id, f"Обновлено: {', '.join(changes)}" if changes else "Обновление", level="info")
    await db.commit()
    await db.refresh(service)
    return service


@router.delete("/services/{service_id}", status_code=204)
async def delete_admin_service(
    service_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Soft-delete a service."""
    service = await get_owned_or_404(db, Service, service_id, master.master_profile.id)
    await log_action(db, master.master_profile.id, "delete", "service", service_id, service.name, level="warning")
    service.is_active = False
    await db.commit()
    return None

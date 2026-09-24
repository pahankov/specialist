"""Admin service CRUD endpoints with pagination."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List

from app.database import get_db
from app.models.service import Service
from app.models.user import User
from app.schemas.service import ServiceCreate, ServiceResponse, ServiceUpdate
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_master
from app.dependencies.crud import get_owned_or_404
from app.services.audit import log_action

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


@router.get("/services", response_model=PaginatedResponse[ServiceResponse])
async def get_admin_services(
    master: User = Depends(require_master),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    active_only: bool = Query(True, description="Return only active services"),
    db: AsyncSession = Depends(get_db)
):
    """Get active services (paginated with total count)."""
    offset = (page - 1) * page_size

    # Base query
    base_query = select(Service).where(Service.master_id == master.master_profile.id)
    count_query = select(func.count(Service.id)).where(Service.master_id == master.master_profile.id)

    if active_only:
        base_query = base_query.where(Service.is_active == True)
        count_query = count_query.where(Service.is_active == True)

    # Get total
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Get data
    data_query = base_query.order_by(Service.name).offset(offset).limit(page_size)
    result = await db.execute(data_query)
    services = result.scalars().all()

    return PaginatedResponse(
        items=services,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )


@router.get("/services/all", response_model=PaginatedResponse[ServiceResponse])
async def get_all_admin_services(
    master: User = Depends(require_master),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    db: AsyncSession = Depends(get_db)
):
    """Get all services including inactive (paginated with total count)."""
    offset = (page - 1) * page_size

    # Get total
    total_result = await db.execute(
        select(func.count(Service.id)).where(Service.master_id == master.master_profile.id)
    )
    total = total_result.scalar() or 0

    # Get data
    result = await db.execute(
        select(Service).where(Service.master_id == master.master_profile.id)
        .order_by(Service.name).offset(offset).limit(page_size)
    )
    services = result.scalars().all()

    return PaginatedResponse(
        items=services,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )


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

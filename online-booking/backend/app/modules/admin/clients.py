"""Admin client CRUD endpoints with pagination."""
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from typing import List, Optional

from app.database import get_db
from app.models.client_profile import ClientProfile
from app.models.user import User
from app.models.appointment import Appointment
from app.schemas.client import ClientCreate, ClientUpdate, ClientResponse
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_master
from app.dependencies.crud import get_or_404
from app.services.audit import log_action

router = APIRouter()


@router.get("/clients", response_model=PaginatedResponse[ClientResponse])
async def get_admin_clients(
    master: User = Depends(require_master),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    search: Optional[str] = Query(None, description="Search by name or phone"),
    master_id: Optional[int] = Query(None, description="Filter by master ID (clients who booked with this master)"),
    db: AsyncSession = Depends(get_db)
):
    """Get all clients (paginated with total count)."""
    offset = (page - 1) * page_size

    # Base query
    base_query = (
        select(ClientProfile)
        .join(ClientProfile.user)
        .options(joinedload(ClientProfile.user))
    )

    is_admin = master.role == User.Role.ADMIN if hasattr(User, 'Role') else master.role.value == "ADMIN" if hasattr(master.role, 'value') else master.role == "ADMIN"
    
    # If master_id filter is specified, only return clients who have appointments with this master
    if master_id is not None:
        base_query = base_query.where(
            ClientProfile.id.in_(
                select(Appointment.client_id).where(Appointment.master_id == master_id)
            )
        )

    # Search filter
    if search:
        search_term = f"%{search}%"
        base_query = base_query.where(
            (User.name.ilike(search_term)) | (User.phone.ilike(search_term))
        )

    # Count total
    count_query = select(func.count(ClientProfile.id)).select_from(base_query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Data query
    data_query = (
        base_query
        .order_by(User.name)
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_query)
    profiles = result.scalars().unique().all()

    # Build response
    items = [
        {
            "id": cp.user.id,
            "name": cp.user.name,
            "phone": cp.user.phone,
            "email": cp.user.email,
            "no_show_count": cp.no_show_count or 0,
            "created_at": cp.user.created_at.isoformat() if cp.user.created_at else None,
            "updated_at": cp.user.updated_at.isoformat() if cp.user.updated_at else None,
        }
        for cp in profiles
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )


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

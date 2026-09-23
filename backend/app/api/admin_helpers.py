"""Generic CRUD helpers for admin endpoints."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from typing import TypeVar, Generic, Optional


T = TypeVar("T")


async def get_owned_or_404(
    db: AsyncSession,
    model: type,
    obj_id: int,
    master_id: int,
    master_field: str = "master_id"
) -> T:
    """Fetch object and verify it belongs to the master. Returns 404 if not found."""
    result = await db.execute(
        select(model).where(
            getattr(model, master_field) == master_id,
            model.id == obj_id
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj  # type: ignore


async def get_or_404(
    db: AsyncSession,
    model: type,
    obj_id: int
) -> T:
    """Fetch any object by ID. Returns 404 if not found."""
    result = await db.execute(
        select(model).where(model.id == obj_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    return obj  # type: ignore


async def soft_delete(
    obj: T,
    db: AsyncSession,
    field: str = "is_active"
) -> None:
    """Soft-delete object by setting is_active=False."""
    setattr(obj, field, False)
    await db.flush()

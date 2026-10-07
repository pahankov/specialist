"""Generic CRUD helpers for all modules."""
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import TypeVar

T = TypeVar("T")


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

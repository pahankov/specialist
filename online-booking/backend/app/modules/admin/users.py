"""Superadmin participant actions that are not tied to a master profile."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_super_admin
from app.models.user import User
from app.services.impersonation import impersonate_user

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/{user_id}/impersonate")
async def impersonate_participant(
    user_id: int,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Log in as any participant (master or client) for support.

    ``user_id`` is the shared ``users.id`` (what admin listings return for
    clients and what ``Master.user_id`` carries for masters).
    """
    target = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return await impersonate_user(db, admin, target)

"""Superadmin security actions: impersonation, password reset, session revoke."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_super_admin
from app.models.master_profile import MasterProfile
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.utils.tokens import create_access_token  # utils, not modules.auth (no module→module import)
from app.services.audit import log_action
from app.utils.security import hash_password, validate_password_strength
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/masters", tags=["masters"])


class PasswordReset(BaseModel):
    password: str


async def _get_master_user(
    db: AsyncSession, master_id: int
) -> tuple[User, MasterProfile]:
    """Load (User, MasterProfile) by profile id. master_id here is ALWAYS
    MasterProfile.id (consistent with the rest of the masters module)."""
    result = await db.execute(
        select(MasterProfile).where(MasterProfile.id == master_id)
    )
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    result = await db.execute(select(User).where(User.id == profile.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user, profile


def _forbid_admin_target(user: User) -> None:
    """Impersonation/password-reset/sessions target must not be a fellow admin."""
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Действие недоступно для учётных записей администраторов",
        )


@router.post("/{master_id}/impersonate")
async def impersonate_master(
    master_id: int,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Issue a short-lived access token for a master (support view-as).

    The token carries `impersonated_by` so the audit trail stays honest.
    Target must be an active non-admin user.
    """
    user, _profile = await _get_master_user(db, master_id)
    _forbid_admin_target(user)
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Пользователь заблокирован")

    token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "is_admin": False,
        "impersonated_by": admin.id,
    })
    await log_action(
        db, admin.id, "impersonate", "user", user.id,
        f"Вход от имени {user.email}", level="warning",
    )
    await db.commit()
    logger.warning("Impersonation: admin %s entered master %s", admin.id, user.id)
    return {"access_token": token, "user_id": user.id, "name": user.name}


@router.patch("/{master_id}/password")
async def reset_master_password(
    master_id: int,
    body: PasswordReset,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Set a new password for a master (support quick action).

    Revokes all sessions so stale logins die immediately.
    """
    user, _profile = await _get_master_user(db, master_id)
    _forbid_admin_target(user)
    try:
        validate_password_strength(body.password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    user.hashed_password = hash_password(body.password)
    revoked = await _revoke_sessions(db, user.id)
    await log_action(
        db, admin.id, "password_reset", "user", user.id,
        f"Сброс пароля ({revoked} сессий отозвано)", level="warning",
    )
    await db.commit()
    logger.warning("Password reset by admin %s for user %s", admin.id, user.id)
    return {"detail": "Пароль обновлён", "sessions_revoked": revoked}


@router.get("/{master_id}/sessions")
async def list_master_sessions(
    master_id: int,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """List active sessions. Token values are NEVER returned."""
    user, _profile = await _get_master_user(db, master_id)
    _forbid_admin_target(user)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id,
            RefreshToken.is_revoked == False,  # noqa: E712
            RefreshToken.expires_at > now,
        ).order_by(RefreshToken.created_at.desc())
    )
    return [
        {"id": t.id, "created_at": t.created_at, "expires_at": t.expires_at}
        for t in result.scalars().all()
    ]


@router.delete("/{master_id}/sessions")
async def revoke_master_sessions(
    master_id: int,
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Revoke all sessions of a master (force logout everywhere)."""
    user, _profile = await _get_master_user(db, master_id)
    _forbid_admin_target(user)
    revoked = await _revoke_sessions(db, user.id)
    await log_action(
        db, admin.id, "sessions_revoke", "user", user.id,
        f"Отозвано сессий: {revoked}", level="warning",
    )
    await db.commit()
    return {"detail": "Сессии отозваны", "revoked": revoked}


async def _revoke_sessions(db: AsyncSession, user_id: int) -> int:
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
        .values(is_revoked=True, revoked_at=now)
    )
    return result.rowcount or 0

"""Support impersonation for any non-admin participant.

A superadmin may open the panel/cabinet as a master or a client. The
issued access token carries ``impersonated_by`` so every downstream audit
trail can tell a support session apart from a real login. Admin accounts
are never impersonatable (an admin could otherwise hide behind another
admin's actions).

The endpoint layer only resolves the target user; token issuance, role
validation, audit logging and the landing route live here so the legacy
``/admin/masters/{id}/impersonate`` and the generic
``/admin/users/{id}/impersonate`` endpoints cannot drift apart.
"""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.user import User, UserRole
from app.services.audit import log_action
from app.utils.tokens import create_access_token

logger = get_logger(__name__)

# Where the frontend sends the superadmin after the token swap.
ROLE_LANDING = {
    UserRole.MASTER: "/admin/dashboard",
    UserRole.CLIENT: "/cabinet",
}


def _forbid_admin_target(user: User) -> None:
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=403,
            detail="Действие недоступно для учётных записей администраторов",
        )


async def impersonate_user(
    db: AsyncSession,
    admin: User,
    target: User,
) -> dict:
    """Issue a short-lived participant token for a superadmin support session."""
    _forbid_admin_target(target)
    if not target.is_active:
        raise HTTPException(status_code=403, detail="Пользователь заблокирован")

    token = create_access_token({
        "sub": str(target.id),
        "role": target.role.value,
        "name": target.name,
        "last_name": target.last_name,
        "is_admin": False,
        "impersonated_by": admin.id,
    })
    await log_action(
        db, admin.id, "impersonate", "user", target.id,
        f"Вход от имени {target.email or target.phone or target.id}",
        level="warning",
    )
    await db.commit()
    logger.warning(
        "Impersonation: admin %s entered user %s (role=%s)",
        admin.id, target.id, target.role.value,
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": target.id,
        "name": target.name,
        "role": target.role.value,
        "redirect": ROLE_LANDING.get(target.role, "/"),
    }

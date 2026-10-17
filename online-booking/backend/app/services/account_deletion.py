"""Self-service account deletion (soft delete + PII anonymization).

The account becomes unusable immediately (is_active=False, sessions revoked,
future appointments cancelled) while rows stay for the 3-year retention
promised in /privacy. Past history is kept readable for the other party.
"""
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.services.audit import log_action
from app.utils import localnow_naive

logger = get_logger(__name__)

# Bookable states that still lie ahead; everything else (completed, cancelled,
# no_show) is history and stays untouched.
LIVE_STATUSES = ("pending", "confirmed")


async def delete_own_account(db: AsyncSession, user: User) -> dict:
    """Deactivate own account, anonymize PII, cancel future appointments."""
    if user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=400,
            detail="Администратор не может удалить себя. "
                   "Попросите другого администратора.",
        )
    if user.is_active is False:
        raise HTTPException(status_code=400, detail="Аккаунт уже удалён")

    now = localnow_naive()
    cancelled = 0

    if user.role == UserRole.MASTER:
        mp = (await db.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one_or_none()
        if mp is not None:
            mp.is_active = False
            mp.status = "inactive"
            res = await db.execute(
                update(Appointment)
                .where(
                    Appointment.master_id == mp.id,
                    Appointment.status.in_(LIVE_STATUSES),
                    Appointment.appointment_date > now,
                )
                .values(status="cancelled")
            )
            cancelled = res.rowcount or 0
    elif user.role == UserRole.CLIENT:
        cp = (await db.execute(
            select(ClientProfile).where(ClientProfile.user_id == user.id)
        )).scalar_one_or_none()
        if cp is not None:
            res = await db.execute(
                update(Appointment)
                .where(
                    Appointment.client_id == cp.id,
                    Appointment.status.in_(LIVE_STATUSES),
                    Appointment.appointment_date > now,
                )
                .values(status="cancelled")
            )
            cancelled = res.rowcount or 0

    # Revoke sessions (access tokens die on the is_active guard in
    # get_current_user / get_current_client).
    await db.execute(
        RefreshToken.__table__.delete().where(RefreshToken.user_id == user.id)
    )

    user.is_active = False
    user.deleted_at = now
    user.email = None
    user.phone = None
    user.name = "Удалённый аккаунт"
    user.last_name = None
    user.max_user_id = None
    user.max_username = None  # MAX nickname is PII too
    user.vk_user_id = None  # VK binding is a PII identifier too
    user.yandex_user_id = None  # Yandex binding is a PII identifier too
    user.hashed_password = None

    await log_action(db, user.id, "delete", "account", user.id,
                     "Пользователь удалил свой аккаунт", level="warning")
    await db.commit()

    logger.info("User %s (%s) deleted own account, cancelled=%s",
                user.id, user.role.value, cancelled)
    return {"detail": "Аккаунт удалён", "cancelled_appointments": cancelled}

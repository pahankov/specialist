"""Per-master client visibility (hide from my lists, keep history).

Hiding never touches the client's account: they stay active, keep other
masters and their own login. Only the hiding master's lists and displays
are affected; past appointments render as DELETED_CLIENT_NAME.
"""
from sqlalchemy import select, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.master_hidden_client import MasterHiddenClient
from app.models.user import User
from app.services.audit import log_action
from app.utils import utcnow

logger = get_logger(__name__)

LIVE_STATUSES = ("pending", "confirmed")


async def hidden_client_profile_ids(db: AsyncSession, master_profile_id: int) -> set:
    """ClientProfile ids hidden by this master (empty set when none)."""
    rows = await db.execute(
        select(MasterHiddenClient.client_profile_id).where(
            MasterHiddenClient.master_profile_id == master_profile_id)
    )
    return {r[0] for r in rows.all()}


async def hide_client_from_master(
    db: AsyncSession, master_user: User, master_profile_id: int,
    client_user: User,
) -> int:
    """Remove a client from one master's lists.

    Cancels the client's future appointments with this master, drops the
    created_by link when it points at this master, and records the hiding
    (idempotent). Returns the number of cancelled appointments.
    """
    now = utcnow()

    cp = (await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == client_user.id)
    )).scalar_one_or_none()

    cancelled = 0
    if cp is not None:
        res = await db.execute(
            update(Appointment)
            .where(
                Appointment.master_id == master_profile_id,
                Appointment.client_id == cp.id,
                Appointment.status.in_(LIVE_STATUSES),
                Appointment.appointment_date > now,
            )
            .values(status="cancelled")
        )
        cancelled = res.rowcount or 0

        exists = (await db.execute(
            select(MasterHiddenClient.id).where(
                MasterHiddenClient.master_profile_id == master_profile_id,
                MasterHiddenClient.client_profile_id == cp.id)
        )).scalar_one_or_none()
        if exists is None:
            db.add(MasterHiddenClient(
                master_profile_id=master_profile_id,
                client_profile_id=cp.id,
            ))

    if client_user.created_by == master_user.id:
        client_user.created_by = None

    await log_action(db, master_user.id, "hide", "client", client_user.id,
                     f"Клиент {client_user.name} убран из списков "
                     f"(история сохранена, отменено записей: {cancelled})",
                     level="warning")
    await db.commit()
    logger.info("Master %s hid client %s, cancelled=%s",
                master_user.id, client_user.id, cancelled)
    return cancelled


async def unhide_client(db: AsyncSession, master_profile_id: int,
                        client_profile_id: int) -> None:
    """Revive visibility after a new booking (no commit — caller owns it)."""
    await db.execute(sa_delete(MasterHiddenClient).where(
        MasterHiddenClient.master_profile_id == master_profile_id,
        MasterHiddenClient.client_profile_id == client_profile_id,
    ))


async def block_client_from_master(
    db: AsyncSession, master_user: User, master_profile_id: int,
    client_user: User,
) -> int:
    """Blacklist: hide + bar new bookings (idempotent).

    Same side effects as hiding (future appointments cancelled, created_by
    dropped), plus the block flag enforced at every booking entry point.
    """
    cancelled = await hide_client_from_master(
        db, master_user, master_profile_id, client_user)
    cp = (await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == client_user.id)
    )).scalar_one_or_none()
    if cp is not None:
        row = (await db.execute(
            select(MasterHiddenClient).where(
                MasterHiddenClient.master_profile_id == master_profile_id,
                MasterHiddenClient.client_profile_id == cp.id)
        )).scalar_one()
        row.is_blocked = True
        row.blocked_at = utcnow()
        await db.commit()
    return cancelled


async def unblock_client(db: AsyncSession, master_profile_id: int,
                         client_profile_id: int) -> bool:
    """Full inverse of block: the client is visible again (commit included).

    Returns True when a hidden row existed.
    """
    res = await db.execute(
        select(MasterHiddenClient.id).where(
            MasterHiddenClient.master_profile_id == master_profile_id,
            MasterHiddenClient.client_profile_id == client_profile_id,
        )
    )
    if res.scalar_one_or_none() is None:
        return False
    await db.execute(sa_delete(MasterHiddenClient).where(
        MasterHiddenClient.master_profile_id == master_profile_id,
        MasterHiddenClient.client_profile_id == client_profile_id,
    ))
    await db.commit()
    return True


async def is_client_blocked(db: AsyncSession, master_profile_id: int,
                            client_profile_id: int) -> bool:
    """True when this master blacklisted this client profile."""
    row = (await db.execute(
        select(MasterHiddenClient.is_blocked).where(
            MasterHiddenClient.master_profile_id == master_profile_id,
            MasterHiddenClient.client_profile_id == client_profile_id)
    )).scalar_one_or_none()
    return bool(row)

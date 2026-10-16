"""Per-master client visibility (archive, blacklist).

Hiding never touches the client's account: they stay active, keep other
masters and their own login. Only the hiding master's lists and displays
are affected; past appointments render as DELETED_CLIENT_NAME.

Archive = hidden with a reason (moved/left/inactive/deceased/other),
retrievable via the master's archive list and restorable.
Blacklist = archive + barred from new bookings.
"""
from typing import Optional
from sqlalchemy import select, update, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.master_hidden_client import MasterHiddenClient
from app.models.user import User
from app.services.audit import log_action
from app.services.booking import format_slot
from app.services.notifications import notify_user
from app.utils import localnow_naive, utcnow

logger = get_logger(__name__)

LIVE_STATUSES = ("pending", "confirmed")

# Client questions go to the admin (no in-app messenger yet).
# TODO: separate support mailbox (currently the owner's personal email).
SUPPORT_CONTACT = "pahankov@mail.ru"

HIDE_REASONS = ("moved", "left", "inactive", "deceased", "other")
BLOCK_REASONS = ("no_show", "rude", "spam", "debt", "other")


async def hidden_client_profile_ids(db: AsyncSession, master_profile_id: int) -> set:
    """ClientProfile ids hidden by this master (empty set when none)."""
    rows = await db.execute(
        select(MasterHiddenClient.client_profile_id).where(
            MasterHiddenClient.master_profile_id == master_profile_id)
    )
    return {r[0] for r in rows.all()}


async def hide_client_from_master(
    db: AsyncSession, master_user: User, master_profile_id: int,
    client_user: User, reason: Optional[str] = None,
    note: Optional[str] = None,
) -> int:
    """Archive a client from one master's lists (idempotent).

    Cancels the client's future appointments with this master, drops the
    created_by link when it points at this master, records the hiding with
    an optional archive reason. Sends ONE summary bell when anything was
    cancelled. Returns the number of cancelled appointments.
    """
    now = localnow_naive()

    cp = (await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == client_user.id)
    )).scalar_one_or_none()

    cancelled = 0
    if cp is not None:
        doomed = (await db.execute(
            select(Appointment).where(
                Appointment.master_id == master_profile_id,
                Appointment.client_id == cp.id,
                Appointment.status.in_(LIVE_STATUSES),
                Appointment.appointment_date > now,
            )
        )).scalars().all()
        if doomed:
            await db.execute(
                update(Appointment)
                .where(Appointment.id.in_([a.id for a in doomed]))
                .values(status="cancelled")
            )
            cancelled = len(doomed)
            await notify_user(
                db, recipient_id=client_user.id,
                text=(f"Мастер {master_user.name} отменил ваши будущие "
                      f"записи ({cancelled}). По вопросам: {SUPPORT_CONTACT}."),
                sender_id=master_user.id, audience="booking",
                link="appointments",
            )

        row = (await db.execute(
            select(MasterHiddenClient).where(
                MasterHiddenClient.master_profile_id == master_profile_id,
                MasterHiddenClient.client_profile_id == cp.id)
        )).scalar_one_or_none()
        if row is None:
            db.add(MasterHiddenClient(
                master_profile_id=master_profile_id,
                client_profile_id=cp.id,
                hidden_reason=reason,
                block_note=(note or "").strip() or None,
            ))
        else:
            if reason:
                row.hidden_reason = reason
            if note is not None:
                row.block_note = note.strip() or None

    if client_user.created_by == master_user.id:
        client_user.created_by = None

    await log_action(db, master_user.id, "hide", "client", client_user.id,
                     f"Клиент {client_user.name} убран в архив "
                     f"(причина: {reason or 'не указана'}, "
                     f"отменено записей: {cancelled})",
                     level="warning")
    await db.commit()
    logger.info("Master %s hid client %s (reason=%s), cancelled=%s",
                master_user.id, client_user.id, reason, cancelled)
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
    client_user: User, reason: Optional[str] = None,
    block_reason: Optional[str] = None, note: Optional[str] = None,
) -> int:
    """Blacklist: archive + bar new bookings (idempotent).

    Sends ONE calm bell: block fact + cancelled count + where to turn
    (admin email — the client contacts only the admin, there is no
    in-app messenger yet).
    """
    cancelled = await hide_client_from_master(
        db, master_user, master_profile_id, client_user, reason, note)
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
        if block_reason:
            row.block_reason = block_reason
        if note is not None:
            row.block_note = note.strip() or None
        await notify_user(
            db, recipient_id=client_user.id,
            text=(f"Мастер {master_user.name} ограничил вам запись: новые "
                  f"записи недоступны."
                  + (f" Отменено будущих записей: {cancelled}." if cancelled else "")
                  + f" Вы можете выбрать другого мастера в каталоге. "
                  f"По вопросам: {SUPPORT_CONTACT}."),
            sender_id=master_user.id, audience="booking",
            link="appointments",
        )
        await db.commit()
    return cancelled


async def unblock_client(db: AsyncSession, master_profile_id: int,
                         client_profile_id: int) -> bool:
    """Full inverse of block/archive: the client is visible again.

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


async def restore_client_appointments(db: AsyncSession, master_profile_id: int,
                                      client_profile_id: int) -> dict:
    """Bring back future appointments killed by a block/archive.

    Only slots that are still free flip to confirmed (the unblock is an
    explicit approval gesture); taken slots stay cancelled. Sends one bell
    when anything was restored. Returns {"restored": n, "skipped": m}.
    """
    from datetime import timedelta
    from app.services.booking import find_conflict, format_slot
    from app.utils import localnow_naive

    now = localnow_naive()
    doomed = (await db.execute(
        select(Appointment).where(
            Appointment.master_id == master_profile_id,
            Appointment.client_id == client_profile_id,
            Appointment.status == "cancelled",
            Appointment.appointment_date > now,
        ).order_by(Appointment.appointment_date)
    )).scalars().all()
    restored = skipped = 0
    for a in doomed:
        dur = a.duration_minutes or 60
        start = a.appointment_date.replace(tzinfo=None)
        clash = await find_conflict(db, master_profile_id, start, int(dur))
        if clash is not None and clash.id != a.id:
            skipped += 1
            continue
        a.status = "confirmed"
        restored += 1
    if restored:
        cp = (await db.execute(
            select(ClientProfile).where(ClientProfile.id == client_profile_id)
        )).scalar_one_or_none()
        if cp is not None:
            await notify_user(
                db, recipient_id=cp.user_id,
                text=(f"Блокировка снята: восстановлено записей: {restored}."
                      + (f" Не влезло в занятые слоты: {skipped}." if skipped else "")),
                audience="booking", link="appointments",
            )
    await db.commit()
    logger.info("Unblock restore: master=%s client_profile=%s restored=%s skipped=%s",
                master_profile_id, client_profile_id, restored, skipped)
    return {"restored": restored, "skipped": skipped}


async def is_client_blocked(db: AsyncSession, master_profile_id: int,
                            client_profile_id: int) -> bool:
    """True when this master blacklisted this client profile."""
    row = (await db.execute(
        select(MasterHiddenClient.is_blocked).where(
            MasterHiddenClient.master_profile_id == master_profile_id,
            MasterHiddenClient.client_profile_id == client_profile_id)
    )).scalar_one_or_none()
    return bool(row)

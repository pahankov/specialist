"""Bell inbox core (services layer, no router deps).

Canonical home for inbox read paths shared by the master/superadmin
panels and the client cabinet. Both `modules/admin/notifications.py`
and `modules/client/router.py` import from here (modules -> services).
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.models.user import User, UserRole


def _to_item(n: Notification, sender_name: Optional[str] = None) -> dict:
    # Never touch n.sender here: on AsyncSession rows the relationship is
    # unloaded and lazy access raises MissingGreenlet (500). Callers pass
    # the pre-resolved name (batched query, no N+1).
    return {
        "id": n.id,
        "text": n.text,
        "audience": n.audience,
        "link": n.link,
        "sender_name": sender_name,
        "is_read": bool(n.is_read),
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


async def _sender_role_filter(exclude: frozenset):
    """SQL fragment: drop bells sent by these roles (NULL senders kept).

    Dual-role users receive both master-bound bells (bookings from clients)
    and client-bound bells (cancels, blocks from masters). Each cabinet
    shows only its own side; the badge counts use the same filter.
    """
    from sqlalchemy import or_ as sa_or
    if not exclude:
        return None
    sub = select(User.id).where(User.role.in_(list(exclude)))
    return sa_or(Notification.sender_id.is_(None),
                 ~Notification.sender_id.in_(sub))


async def _inbox(db: AsyncSession, user: User, unread_only: bool,
                 page: int, page_size: int,
                 exclude_sender_roles: frozenset = frozenset()) -> dict:
    base = select(Notification).where(Notification.recipient_id == user.id)
    scope = await _sender_role_filter(exclude_sender_roles)
    if scope is not None:
        base = base.where(scope)
    if unread_only:
        base = base.where(Notification.is_read == False)  # noqa: E712
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0
    unread_q = select(func.count(Notification.id)).where(
        Notification.recipient_id == user.id,
        Notification.is_read == False,  # noqa: E712
    )
    if scope is not None:
        unread_q = unread_q.where(scope)
    unread = (await db.execute(unread_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    # Bulk sender names (no N+1).
    sender_ids = {n.sender_id for n in rows if n.sender_id}
    names: dict = {}
    if sender_ids:
        srows = await db.execute(select(User.id, User.name).where(User.id.in_(sender_ids)))
        names = dict(srows.all())
    items = []
    for n in rows:
        items.append(_to_item(n, names.get(n.sender_id)))
    return {"items": items, "total": total, "unread": unread,
            "page": page, "page_size": page_size}


async def _mark_read(db: AsyncSession, user: User, notif_id: int) -> dict:
    n = (await db.execute(select(Notification).where(
        Notification.id == notif_id, Notification.recipient_id == user.id))).scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    if not n.is_read:
        n.is_read = True
        n.read_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(n)
    sender_name = None
    if n.sender_id:
        sender_name = (await db.execute(
            select(User.name).where(User.id == n.sender_id)
        )).scalar_one_or_none()
    return _to_item(n, sender_name)


async def client_inbox(db: AsyncSession, user: User, unread_only: bool,
                       page: int, page_size: int) -> dict:
    """Cabinet inbox: master-side bells (bookings to her-as-master) excluded."""
    return await _inbox(db, user, unread_only, page, page_size,
                        frozenset({UserRole.CLIENT}))


async def client_mark_read(db: AsyncSession, user: User, notif_id: int) -> dict:
    return await _mark_read(db, user, notif_id)


async def client_read_all(db: AsyncSession, user: User) -> dict:
    from sqlalchemy import update as sa_update

    await db.execute(
        sa_update(Notification)
        .where(Notification.recipient_id == user.id,
               Notification.is_read == False)  # noqa: E712
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"ok": True}


async def client_unread_count(db: AsyncSession, user: User) -> dict:
    scope = await _sender_role_filter(frozenset({UserRole.CLIENT}))
    q = select(func.count(Notification.id)).where(
        Notification.recipient_id == user.id,
        Notification.is_read == False,  # noqa: E712
    )
    if scope is not None:
        q = q.where(scope)
    unread = (await db.execute(q)).scalar() or 0
    return {"unread": unread}


async def delete_own_notifications(db: AsyncSession, user: User) -> dict:
    """Clear own bell inbox (logout-safe: only recipient's rows)."""
    from sqlalchemy import delete as sa_delete

    res = await db.execute(
        sa_delete(Notification).where(Notification.recipient_id == user.id)
    )
    await db.commit()
    return {"deleted": res.rowcount or 0}

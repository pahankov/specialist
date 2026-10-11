"""Internal bell notifications (no messenger binding).

Superadmin audiences: all / masters / clients / selected user_ids.
Master audiences: my_clients / selected (CLIENT role only).

Broadcast writes one row per recipient into `notifications`;
inbox endpoints serve master/super panels (client cabinet lives
in app.modules.client.router).
"""
from datetime import datetime, timezone
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_master
from app.models.notification import Notification
from app.models.notification_broadcast import NotificationBroadcast
from app.models.user import User, UserRole
from app.modules.admin.helpers import own_client_user_ids
from app.services.audit import log_action
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

Audience = Literal["all", "masters", "clients", "my_clients", "selected"]
MAX_TARGETS = 2000


class BroadcastRequest(BaseModel):
    audience: Audience = Field(description="all|masters|clients|my_clients|selected")
    user_ids: Optional[List[int]] = Field(default=None, description="Required for audience=selected")
    text: str = Field(min_length=1, max_length=4000, description="Message text")


class BroadcastResult(BaseModel):
    total: int
    created: int
    skipped_not_allowed: int = 0


class InboxItem(BaseModel):
    id: int
    text: str
    audience: Optional[str] = None
    sender_name: Optional[str] = None
    is_read: bool
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


async def resolve_targets(
    db: AsyncSession, sender: User, audience: Audience, user_ids: Optional[List[int]]
) -> tuple[list[User], int]:
    """Return (targets, skipped_not_allowed). Raises 403/400 on bad audience."""
    is_admin = sender.role == UserRole.ADMIN

    if audience == "selected":
        if not user_ids:
            raise HTTPException(status_code=400, detail="Укажите user_ids для рассылки")
        uniq = list(dict.fromkeys(user_ids))[:500]
        rows = await db.execute(
            select(User).where(User.id.in_(uniq), User.is_active == True)  # noqa: E712
        )
        users = list(rows.scalars().all())
        if not is_admin:
            # Master: only OWN clients (booked or created) — others are skipped.
            own = await own_client_user_ids(db, sender)
            allowed = [u for u in users
                       if u.role == UserRole.CLIENT and u.id in own]
            return allowed, len(users) - len(allowed)
        return users, 0

    if audience == "my_clients":
        if is_admin:
            raise HTTPException(
                status_code=400,
                detail="Суперпользователь: используйте audiences all/masters/clients/selected",
            )
        own = await own_client_user_ids(db, sender)
        if not own:
            return [], 0
        rows = await db.execute(
            select(User).where(User.id.in_(list(own)), User.is_active == True)  # noqa: E712
        )
        return list(rows.scalars().all()), 0

    if not is_admin:
        raise HTTPException(
            status_code=403, detail="Доступно только суперпользователю (мастер: my_clients/selected)"
        )
    if audience == "all":
        rows = await db.execute(select(User).where(User.is_active == True))  # noqa: E712
        return list(rows.scalars().all()), 0
    if audience == "masters":
        rows = await db.execute(
            select(User).where(
                User.role.in_([UserRole.MASTER, UserRole.ADMIN]),
                User.is_active == True,  # noqa: E712
            )
        )
        return list(rows.scalars().all()), 0
    if audience == "clients":
        rows = await db.execute(
            select(User).where(User.role == UserRole.CLIENT, User.is_active == True)  # noqa: E712
        )
        return list(rows.scalars().all()), 0
    raise HTTPException(status_code=400, detail="Неизвестная аудитория")


def _to_item(n: Notification) -> dict:
    return {
        "id": n.id,
        "text": n.text,
        "audience": n.audience,
        "sender_name": n.sender.name if getattr(n, "sender", None) else None,
        "is_read": bool(n.is_read),
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


async def _inbox(db: AsyncSession, user: User, unread_only: bool,
                 page: int, page_size: int) -> dict:
    base = select(Notification).where(Notification.recipient_id == user.id)
    if unread_only:
        base = base.where(Notification.is_read == False)  # noqa: E712
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0
    unread = (await db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )).scalar() or 0
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
        d = _to_item(n)
        d["sender_name"] = names.get(n.sender_id)
        items.append(d)
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
    return _to_item(n)


@router.get("/notifications/audience-counts")
async def audience_counts(
    audience: Audience = Query(...),
    user_ids: Optional[str] = Query(None, description="Comma-separated ids for selected"),
    sender: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """How many users an audience resolves to."""
    ids = None
    if user_ids:
        try:
            ids = [int(x) for x in user_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="user_ids: числа через запятую")
    targets, skipped = await resolve_targets(db, sender, audience, ids)
    return {"audience": audience, "total": len(targets), "skipped_not_allowed": skipped}


@router.post("/notifications/broadcast", response_model=BroadcastResult)
async def broadcast(
    data: BroadcastRequest,
    sender: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Internal broadcast: one inbox row per recipient (no messenger needed)."""
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст пустой")

    targets, skipped = await resolve_targets(db, sender, data.audience, data.user_ids)
    targets = targets[:MAX_TARGETS]
    now = datetime.now(timezone.utc)
    db.add_all([
        Notification(sender_id=sender.id, recipient_id=u.id,
                     text=text, audience=data.audience, created_at=now)
        for u in targets
    ])
    db.add(NotificationBroadcast(
        sender_id=sender.id, audience=data.audience, text=text,
        recipients=[{"id": u.id, "name": u.name} for u in targets],
        created_at=now,
    ))
    await log_action(
        db, sender.id, "broadcast", "notification", None,
        f"audience={data.audience} recipients={len(targets)}", level="info",
    )
    await db.commit()
    logger.info("Bell broadcast: sender=%s audience=%s recipients=%d",
                sender.id, data.audience, len(targets))
    return BroadcastResult(total=len(targets), created=len(targets), skipped_not_allowed=skipped)


@router.get("/notifications/sent")
async def sent_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sender: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Own sent broadcasts: what/when/to-whom, newest first."""
    base = select(NotificationBroadcast).where(
        NotificationBroadcast.sender_id == sender.id
    )
    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar() or 0
    rows = (await db.execute(
        base.order_by(NotificationBroadcast.created_at.desc(),
                      NotificationBroadcast.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()
    return {
        "items": [
            {
                "id": b.id,
                "audience": b.audience,
                "text": b.text,
                "recipients": b.recipients or [],
                "recipient_count": len(b.recipients or []),
                "created_at": b.created_at.isoformat() if b.created_at else None,
            }
            for b in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/notifications/inbox")
async def admin_inbox(
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Own inbox for master/super panels."""
    return await _inbox(db, user, unread_only, page, page_size)


@router.get("/notifications/unread-count")
async def admin_unread_count(
    user: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Lightweight bell badge poll."""
    unread = (await db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )).scalar() or 0
    return {"unread": unread}


@router.post("/notifications/{notif_id}/read")
async def admin_mark_read(
    notif_id: int,
    user: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    return await _mark_read(db, user, notif_id)


@router.post("/notifications/read-all")
async def admin_read_all(
    user: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import update as sa_update

    await db.execute(
        sa_update(Notification)
        .where(Notification.recipient_id == user.id,
               Notification.is_read == False)  # noqa: E712
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await db.commit()
    return {"ok": True}


# ─── Shared helpers for the client cabinet (any authenticated user) ───

async def client_inbox(db: AsyncSession, user: User, unread_only: bool,
                       page: int, page_size: int) -> dict:
    return await _inbox(db, user, unread_only, page, page_size)


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
    unread = (await db.execute(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user.id,
            Notification.is_read == False,  # noqa: E712
        )
    )).scalar() or 0
    return {"unread": unread}


async def any_user_unread_count(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bell badge for any role (panels + cabinet share one hook)."""
    return await client_unread_count(db, user)

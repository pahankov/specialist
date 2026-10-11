"""Broadcast notifications via MAX bot.

Superadmin audiences: all / masters / clients / selected user_ids.
Master audiences: my_clients (CLIENT-role users with an appointment
with me, plus newcomers I created — resolved as all active CLIENTs
visible to me) / selected (must be CLIENT role).

Delivery is immediate via MaxBotApi.send_message to bound
User.max_user_id. Unbound users are counted as skipped_no_max.
No new tables — sends are audit-logged.
"""
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_master
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.user import User, UserRole
from app.modules.admin.helpers import get_master_profile_id
from app.services.audit import log_action
from app.services.max_api import MaxApiError, get_max_api
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

Audience = Literal["all", "masters", "clients", "my_clients", "selected"]


class BroadcastRequest(BaseModel):
    audience: Audience = Field(description="all|masters|clients|my_clients|selected")
    user_ids: Optional[List[int]] = Field(default=None, description="Required for audience=selected")
    text: str = Field(min_length=1, max_length=4000, description="Message text")


class BroadcastResult(BaseModel):
    total: int
    sent: int
    skipped_no_max: int
    skipped_not_allowed: int = 0


async def _own_client_user_ids(db: AsyncSession, mp_id: int) -> set:
    """User ids of CLIENTs booked with this master profile."""
    rows = await db.execute(
        select(ClientProfile.user_id)
        .join(Appointment, Appointment.client_id == ClientProfile.id)
        .where(Appointment.master_id == mp_id)
    )
    return {r[0] for r in rows.all()}


async def _resolve_targets(
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
        users = rows.scalars().all()
        if not is_admin:
            # Master may message CLIENTs only (mirrors Clients visibility).
            allowed = [u for u in users if u.role == UserRole.CLIENT]
            skipped = len(users) - len(allowed)
            return allowed, skipped
        return list(users), 0

    if audience == "my_clients":
        if is_admin:
            raise HTTPException(
                status_code=400,
                detail="Суперпользователь: используйте audiences all/masters/clients/selected",
            )
        mp_id = await get_master_profile_id(db, sender)
        own = await _own_client_user_ids(db, mp_id)
        if own:
            rows = await db.execute(
                select(User).where(User.id.in_(list(own)), User.is_active == True)  # noqa: E712
            )
            return list(rows.scalars().all()), 0
        # New master with no bookings yet: fall back to visible CLIENTs
        # so the first announcement is still possible.
        rows = await db.execute(
            select(User).where(User.role == UserRole.CLIENT, User.is_active == True)  # noqa: E712
        )
        return list(rows.scalars().all()), 0

    # Preset audiences are superadmin-only.
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


@router.get("/notifications/audience-counts")
async def audience_counts(
    audience: Audience = Query(...),
    user_ids: Optional[str] = Query(None, description="Comma-separated ids for selected"),
    sender: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """How many users an audience resolves to (and how many have MAX bound)."""
    ids = None
    if user_ids:
        try:
            ids = [int(x) for x in user_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="user_ids: числа через запятую")
    targets, skipped = await _resolve_targets(db, sender, audience, ids)
    with_max = sum(1 for u in targets if u.max_user_id is not None)
    return {
        "audience": audience,
        "total": len(targets),
        "with_max": with_max,
        "without_max": len(targets) - with_max,
        "skipped_not_allowed": skipped,
    }


@router.post("/notifications/broadcast", response_model=BroadcastResult)
async def broadcast(
    data: BroadcastRequest,
    sender: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Send text to an audience via MAX bot (immediate, audit-logged)."""
    text = data.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Текст пустой")

    api = get_max_api()
    if not api.enabled:
        raise HTTPException(status_code=503, detail="MAX_BOT_TOKEN не настроен")

    targets, skipped_not_allowed = await _resolve_targets(db, sender, data.audience, data.user_ids)

    sent = 0
    skipped_no_max = 0
    for u in targets:
        if u.max_user_id is None:
            skipped_no_max += 1
            continue
        try:
            await api.send_message(int(u.max_user_id), text)
            sent += 1
        except MaxApiError as e:
            logger.warning("Broadcast to user=%s failed: %s", u.id, e)
            skipped_no_max += 1

    await log_action(
        db, sender.id, "broadcast", "notification", None,
        f"audience={data.audience} total={len(targets)} sent={sent} no_max={skipped_no_max}",
        level="info",
    )
    await db.commit()
    logger.info(
        "Broadcast: sender=%s audience=%s total=%d sent=%d no_max=%d",
        sender.id, data.audience, len(targets), sent, skipped_no_max,
    )
    return BroadcastResult(
        total=len(targets), sent=sent,
        skipped_no_max=skipped_no_max, skipped_not_allowed=skipped_not_allowed,
    )

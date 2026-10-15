"""Personal coupons: master issues -% / -RUB codes to own clients.

Creation notifies the audience with a bell (code + terms). Clients apply
the code in the cabinet promo field; preview shows the new total before
booking, and the booking snapshots the discounted price.
"""
import secrets
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_master
from app.models.coupon import Coupon, CouponUse
from app.models.user import User
from app.modules.admin.helpers import get_master_profile_id, own_client_user_ids
from app.services.audit import log_action
from app.services.notifications import notify_user
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _gen_code() -> str:
    raw = "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def _norm_code(code: str) -> str:
    return (code or "").strip().upper().replace(" ", "").replace("‐", "-")


def coupon_to_dict(c: Coupon) -> dict:
    return {
        "id": c.id,
        "master_id": c.master_id,
        "code": c.code,
        "kind": c.kind,
        "value": float(c.value or 0),
        "max_uses": c.max_uses,
        "used_count": c.used_count or 0,
        "uses_left": (c.max_uses - (c.used_count or 0)) if c.max_uses else None,
        "audience": "selected" if c.user_ids else "my_clients",
        "user_ids": c.user_ids or [],
        "valid_until": c.valid_until.isoformat() if c.valid_until else None,
        "is_active": bool(c.is_active),
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def describe_coupon(c: Coupon) -> str:
    if c.kind == "percent":
        return f"−{int(float(c.value or 0))}%"
    return f"−{int(float(c.value or 0))} ₽"


class CouponCreate(BaseModel):
    code: Optional[str] = Field(default=None, max_length=24)
    kind: str = Field(default="percent", pattern="^(percent|fixed)$")
    value: float = Field(gt=0)
    max_uses: Optional[int] = Field(default=None, ge=1, le=10000)
    user_ids: Optional[List[int]] = Field(default=None)
    valid_until: Optional[datetime] = Field(default=None)


@router.post("/coupons", status_code=201)
async def create_coupon(
    data: CouponCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Issue a coupon to own clients (bell with the code goes out)."""
    from app.models.user import UserRole

    mp_id = await get_master_profile_id(db, master)
    if data.kind == "percent" and not (0 < data.value <= 90):
        raise HTTPException(status_code=400, detail="Процент — от 1 до 90")
    if data.kind == "fixed" and not (data.value > 0):
        raise HTTPException(status_code=400, detail="Сумма купона больше 0")

    code = _norm_code(data.code) if data.code else _gen_code()
    if not code or len(code) < 4:
        raise HTTPException(status_code=400, detail="Код слишком короткий")
    dup = (await db.execute(
        select(Coupon).where(Coupon.master_id == mp_id, Coupon.code == code)
    )).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(status_code=409, detail="Такой код уже есть")

    targets: list[User] = []
    user_ids = None
    if data.user_ids:
        own = await own_client_user_ids(db, master)
        allowed = [uid for uid in dict.fromkeys(data.user_ids) if uid in own]
        if not allowed:
            raise HTTPException(status_code=400, detail="Нет своих клиентов в списке")
        rows = (await db.execute(
            select(User).where(User.id.in_(allowed),
                               User.role == UserRole.CLIENT,
                               User.is_active == True)  # noqa: E712
        )).scalars().all()
        targets = list(rows)
        user_ids = [u.id for u in targets]
    else:
        own = await own_client_user_ids(db, master)
        if own:
            rows = (await db.execute(
                select(User).where(User.id.in_(list(own)),
                                   User.role == UserRole.CLIENT,
                                   User.is_active == True)  # noqa: E712
            )).scalars().all()
            targets = list(rows)

    c = Coupon(master_id=mp_id, code=code, kind=data.kind, value=data.value,
               max_uses=data.max_uses, used_count=0, user_ids=user_ids,
               valid_until=data.valid_until.replace(tzinfo=None) if data.valid_until else None,
               is_active=True)
    db.add(c)
    await db.flush()

    until = (f" до {c.valid_until.strftime('%d.%m')}" if c.valid_until else "")
    text = (f"🎟 Ваш купон {describe_coupon(c)} от {master.name}: код {code}{until}. "
            f"Введите его в поле «Промокод» при записи.")
    for u in targets:
        await notify_user(db, recipient_id=u.id, text=text,
                          sender_id=master.id, audience="coupon",
                          link=f"book:{mp_id}")
    await log_action(db, master.id, "create", "coupon", c.id,
                     f"{code} {describe_coupon(c)} получателей={len(targets)}",
                     level="info")
    await db.commit()
    await db.refresh(c)
    logger.info("Coupon %s issued by master %s to %s clients",
                code, master.id, len(targets))
    return {**coupon_to_dict(c), "notified": len(targets)}


@router.get("/coupons")
async def list_coupons(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Own coupons, newest first."""
    mp_id = await get_master_profile_id(db, master)
    rows = (await db.execute(
        select(Coupon).where(Coupon.master_id == mp_id)
        .order_by(Coupon.id.desc())
    )).scalars().all()
    return [coupon_to_dict(c) for c in rows]


@router.delete("/coupons/{coupon_id}")
async def deactivate_coupon(
    coupon_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Switch a coupon off (history kept, code stops working)."""
    mp_id = await get_master_profile_id(db, master)
    c = (await db.execute(
        select(Coupon).where(Coupon.id == coupon_id, Coupon.master_id == mp_id)
    )).scalar_one_or_none()
    if c is None:
        raise HTTPException(status_code=404, detail="Купон не найден")
    c.is_active = False
    await log_action(db, master.id, "delete", "coupon", c.id, c.code, level="warning")
    await db.commit()
    return {"ok": True}


# ─── Shared validation for preview + booking ───

async def resolve_coupon(db: AsyncSession, master_profile_id: int,
                         code: str, user: User) -> Coupon:
    """Find a usable coupon or raise a client-friendly error."""
    c = (await db.execute(
        select(Coupon).where(Coupon.master_id == master_profile_id,
                             Coupon.code == _norm_code(code))
    )).scalar_one_or_none()
    if c is None or c.is_active is not True:
        raise HTTPException(status_code=404, detail="Купон не найден")
    if c.valid_until is not None:
        from app.utils import localnow_naive
        end = c.valid_until.replace(tzinfo=None)
        if localnow_naive() >= end:
            raise HTTPException(status_code=400, detail="Срок купона истёк")
    if c.max_uses and (c.used_count or 0) >= c.max_uses:
        raise HTTPException(status_code=400, detail="Купон уже использован")
    if c.user_ids and user.id not in c.user_ids:
        raise HTTPException(status_code=403, detail="Купон не для вас")
    return c


def coupon_discount(base_price: float, c: Coupon) -> float:
    """RUB off the base price (never below zero)."""
    base = round(float(base_price or 0), 2)
    if c.kind == "percent":
        return round(base * float(c.value or 0) / 100, 2)
    return round(min(base, float(c.value or 0)), 2)

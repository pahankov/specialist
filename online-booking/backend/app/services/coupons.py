"""Coupon validation + math (services layer, no router deps).

Canonical home for coupon helpers shared by the admin coupons router
(issue/list) and the client cabinet (preview/booking). Both import
from here (modules -> services).
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coupon import Coupon
from app.models.user import User


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

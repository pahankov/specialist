"""Pure bundle duration helpers (services layer, no router deps).

Canonical home for bundle duration math shared by the admin bundles
router and the booking service. Pure functions over ServiceBundle —
no FastAPI/DB imports, so services may use them without depending
upward on modules (modules -> services only).
"""
from typing import Dict

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.service import Service
from app.models.service_bundle import ServiceBundle
from app.services.pricing import apply_discount, clamp_discount


def effective_durations(bundle: ServiceBundle) -> Dict[int, int]:
    """Member durations with per-service overrides applied (keys may be str)."""
    raw = bundle.durations or {}
    return {int(k): int(v) for k, v in raw.items()}


def bundle_total_minutes(bundle: ServiceBundle, members_sum: int) -> int:
    """Manual total wins; otherwise the member sum (complexes are faster)."""
    if bundle.duration_override is not None:
        return int(bundle.duration_override)
    return members_sum


async def _own_services(db: AsyncSession, mp_id: int, service_ids: list[int]) -> list[Service]:
    """Validate ids: own + existing (order preserved, dupes dropped)."""
    ordered = list(dict.fromkeys(service_ids))
    rows = (await db.execute(
        select(Service).where(Service.id.in_(ordered), Service.master_id == mp_id)
    )).scalars().all()
    if len(rows) != len(ordered):
        raise HTTPException(status_code=404, detail="Услуга не найдена")
    by_id = {s.id: s for s in rows}
    return [by_id[i] for i in ordered]


async def bundle_to_dict(db: AsyncSession, b: ServiceBundle) -> dict:
    """Full bundle view with computed totals (admin + cabinet share it)."""
    services = await _own_services(db, b.master_id, b.service_ids or [])
    overrides = effective_durations(b)
    items = [
        {"id": s.id, "name": s.name,
         "duration_minutes": overrides.get(s.id, s.duration_minutes or 0),
         "base_duration_minutes": s.duration_minutes or 0,
         "price": float(s.price or 0),
         "discount_percent": clamp_discount(s.discount_percent),
         "effective_price": s.effective_price}
        for s in services
    ]
    duration_total = bundle_total_minutes(
        b, sum(i["duration_minutes"] for i in items))
    price_total = sum(float(s.price or 0) for s in services)
    members_effective = sum(i["effective_price"] for i in items)
    base = float(b.price) if b.price is not None else round(members_effective, 2)
    return {
        "id": b.id,
        "master_id": b.master_id,
        "name": b.name,
        "service_ids": b.service_ids or [],
        "durations": {str(k): v for k, v in overrides.items()},
        "services": items,
        "duration_total": duration_total,
        "duration_override": b.duration_override,
        "price_total": round(price_total, 2),
        # Custom price wins; NULL = sum of member effective prices.
        "price": float(b.price) if b.price is not None else None,
        "discount_percent": clamp_discount(b.discount_percent),
        "discount_until": b.discount_until.isoformat() if b.discount_until else None,
        "discount_fixed": float(b.discount_fixed or 0),
        "effective_price": apply_discount(base, b.discount_percent,
                                          b.discount_until, b.discount_fixed),
        "is_active": bool(b.is_active),
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }

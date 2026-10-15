"""Master service bundles (complexes): named sets of own services.

Separate feature from services: bundles never mix into the services list;
they are assembled from created services and booked as ONE appointment
(durations sum up, price is custom or the sum).
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.database import get_db
from app.dependencies.auth import require_master
from app.models.master_profile import MasterProfile
from app.models.service import Service
from app.models.service_bundle import ServiceBundle
from app.models.user import User, UserRole
from app.modules.admin.helpers import get_master_profile_id
from app.services.audit import log_action
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()

MIN_DURATION = 5
MAX_DURATION = 480


class BundleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    service_ids: List[int] = Field(min_length=2, max_length=20)
    durations: Optional[Dict[int, int]] = Field(default=None)
    price: Optional[float] = Field(default=None, ge=0)
    duration_override: Optional[int] = Field(default=None)
    discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    discount_until: Optional[datetime] = Field(default=None)
    discount_fixed: Optional[float] = Field(default=None, ge=0)


class BundleUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    service_ids: Optional[List[int]] = Field(default=None, min_length=2, max_length=20)
    durations: Optional[Dict[int, int]] = Field(default=None)
    price: Optional[float] = Field(default=None, ge=0)
    duration_override: Optional[int] = Field(default=None)
    discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    discount_until: Optional[datetime] = Field(default=None)
    discount_fixed: Optional[float] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


def effective_durations(bundle: ServiceBundle) -> Dict[int, int]:
    """Member durations with per-service overrides applied (keys may be str)."""
    raw = bundle.durations or {}
    return {int(k): int(v) for k, v in raw.items()}


def bundle_total_minutes(bundle: ServiceBundle, members_sum: int) -> int:
    """Manual total wins; otherwise the member sum (complexes are faster)."""
    if bundle.duration_override is not None:
        return int(bundle.duration_override)
    return members_sum


def validate_durations(service_ids: list[int],
                       durations: Optional[Dict[int, int]]) -> dict:
    """Override map: subset of members, sane minutes. Stored with int keys."""
    if not durations:
        return {}
    out = {}
    for k, v in durations.items():
        try:
            sid, mins = int(k), int(v)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Некорректное время услуги")
        if sid not in service_ids:
            raise HTTPException(status_code=400, detail="Время для услуги вне комплекса")
        if not (MIN_DURATION <= mins <= MAX_DURATION):
            raise HTTPException(
                status_code=400,
                detail=f"Время услуги — от {MIN_DURATION} до {MAX_DURATION} мин",
            )
        out[sid] = mins
    return out


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


async def _bundle_to_dict(db: AsyncSession, b: ServiceBundle) -> dict:
    from app.services.pricing import apply_discount, clamp_discount

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


async def _get_owned(db: AsyncSession, mp_id: int, bundle_id: int) -> ServiceBundle:
    b = (await db.execute(
        select(ServiceBundle).where(ServiceBundle.id == bundle_id,
                                    ServiceBundle.master_id == mp_id)
    )).scalar_one_or_none()
    if b is None:
        raise HTTPException(status_code=404, detail="Комплекс не найден")
    return b


@router.post("/bundles", status_code=201)
async def create_bundle(
    data: BundleCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Assemble a complex from own services (min 2)."""
    mp_id = await get_master_profile_id(db, master)
    services = await _own_services(db, mp_id, data.service_ids)
    ids = [s.id for s in services]
    if data.duration_override is not None and not (
            MIN_DURATION <= data.duration_override <= MAX_DURATION):
        raise HTTPException(
            status_code=400,
            detail=f"Время комплекса — от {MIN_DURATION} до {MAX_DURATION} мин",
        )
    b = ServiceBundle(
        master_id=mp_id, name=data.name.strip(),
        service_ids=ids,
        durations=validate_durations(ids, data.durations),
        duration_override=data.duration_override,
        discount_percent=data.discount_percent or 0,
        discount_until=data.discount_until,
        discount_fixed=data.discount_fixed or 0,
        price=data.price, is_active=True,
    )
    db.add(b)
    await db.flush()
    await log_action(db, master.id, "create", "bundle", b.id, b.name, level="info")
    await db.commit()
    await db.refresh(b)
    return await _bundle_to_dict(db, b)


@router.get("/bundles")
async def list_bundles(
    master: User = Depends(require_master),
    master_id: Optional[int] = Query(
        default=None,
        description="Superadmin only: MasterProfile.id to list for."),
    db: AsyncSession = Depends(get_db),
):
    """Own complexes (active and inactive), with computed totals."""
    if master_id is not None:
        if master.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Только для суперадмина")
        mp_id = master_id
    else:
        mp_id = await get_master_profile_id(db, master)
    rows = (await db.execute(
        select(ServiceBundle).where(ServiceBundle.master_id == mp_id)
        .order_by(ServiceBundle.name)
    )).scalars().all()
    return [await _bundle_to_dict(db, b) for b in rows]


@router.patch("/bundles/{bundle_id}")
async def update_bundle(
    bundle_id: int,
    data: BundleUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    mp_id = await get_master_profile_id(db, master)
    b = await _get_owned(db, mp_id, bundle_id)
    if data.name is not None:
        b.name = data.name.strip()
    if data.service_ids is not None:
        services = await _own_services(db, mp_id, data.service_ids)
        ids = [s.id for s in services]
        b.service_ids = ids
        # Composition changed: drop overrides for removed members, then
        # validate the rest (explicit durations map wins over stored one).
        stored = {int(k): int(v) for k, v in (b.durations or {}).items()
                  if int(k) in ids}
        incoming = data.durations if "durations" in data.model_fields_set else None
        b.durations = validate_durations(
            ids, incoming if incoming is not None else stored)
    elif "durations" in data.model_fields_set:
        b.durations = validate_durations(b.service_ids or [], data.durations)
    if "price" in data.model_fields_set:
        b.price = data.price
    if "discount_percent" in data.model_fields_set:
        b.discount_percent = data.discount_percent or 0
    if "discount_until" in data.model_fields_set:
        b.discount_until = data.discount_until
    if "discount_fixed" in data.model_fields_set:
        b.discount_fixed = data.discount_fixed or 0
    if "duration_override" in data.model_fields_set:
        ov = data.duration_override
        if ov is not None and not (MIN_DURATION <= ov <= MAX_DURATION):
            raise HTTPException(
                status_code=400,
                detail=f"Время комплекса — от {MIN_DURATION} до {MAX_DURATION} мин",
            )
        b.duration_override = ov
    if data.is_active is not None:
        b.is_active = data.is_active
    await log_action(db, master.id, "update", "bundle", b.id, b.name, level="info")
    await db.commit()
    await db.refresh(b)
    return await _bundle_to_dict(db, b)


@router.delete("/bundles/{bundle_id}", status_code=204)
async def delete_bundle(
    bundle_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Hard delete; past appointments keep bundle_name snapshot + NULL link."""
    mp_id = await get_master_profile_id(db, master)
    b = await _get_owned(db, mp_id, bundle_id)
    await log_action(db, master.id, "delete", "bundle", b.id, b.name, level="warning")
    await db.delete(b)
    await db.commit()
    return None

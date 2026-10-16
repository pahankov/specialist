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
from app.services.bundles import (
    _own_services,
    bundle_to_dict,
    bundle_total_minutes,
    effective_durations,
)
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
    return await bundle_to_dict(db, b)


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
    return [await bundle_to_dict(db, b) for b in rows]


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
    return await bundle_to_dict(db, b)


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

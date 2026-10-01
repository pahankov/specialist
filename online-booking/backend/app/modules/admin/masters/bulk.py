"""Bulk master operations — toggle, suspend, unsuspend for multiple masters."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from typing import List

from app.database import get_db
from app.models.user import User
from app.models.master_profile import MasterProfile
from app.dependencies.auth import require_super_admin
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


async def _get_master_or_404(db, master_id: int):
    """Load MasterProfile with User or raise 404."""
    result = await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )
    mp = result.scalar_one_or_none()
    if not mp:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    return mp


@router.post("/bulk/toggle-active", response_model=dict)
async def bulk_toggle_active(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Toggle active status for multiple masters at once."""
    logger.info(
        "Bulk toggle-active: admin=%s, masters=%s",
        super_admin.email, master_ids
    )
    results = {"toggled": [], "errors": []}

    for mid in master_ids:
        try:
            mp = await _get_master_or_404(db, mid)
            if mp.user.id == super_admin.id:
                logger.warning("Bulk toggle: admin %s tried to toggle self (id=%s)", super_admin.email, mid)
                results["errors"].append({"master_id": mid, "error": "Cannot toggle self"})
                continue

            old_status = mp.status
            mp.status = "inactive" if mp.status == "active" else "active"
            new_status = mp.status
            logger.info(
                "Bulk toggle: master id=%s (%s) %s → %s",
                mid, mp.user.name, old_status, new_status
            )
            results["toggled"].append({
                "master_id": mid,
                "name": mp.user.name,
                "new_status": new_status
            })
        except HTTPException as e:
            logger.warning("Bulk toggle: master id=%s error: %s", mid, e.detail)
            results["errors"].append({"master_id": mid, "error": e.detail})
        except Exception as e:
            logger.error("Bulk toggle: master id=%s unexpected error: %s", mid, e, exc_info=True)
            results["errors"].append({"master_id": mid, "error": str(e)})

    logger.info(
        "Bulk toggle complete: admin=%s, toggled=%d, errors=%d",
        super_admin.email, len(results["toggled"]), len(results["errors"])
    )
    await db.commit()
    return results


@router.post("/bulk/suspend", response_model=dict)
async def bulk_suspend(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend multiple masters at once."""
    logger.info(
        "Bulk suspend: admin=%s, masters=%s",
        super_admin.email, master_ids
    )
    results = {"suspended": [], "errors": []}

    for mid in master_ids:
        try:
            mp = await _get_master_or_404(db, mid)
            if mp.user.id == super_admin.id:
                logger.warning("Bulk suspend: admin %s tried to suspend self (id=%s)", super_admin.email, mid)
                results["errors"].append({"master_id": mid, "error": "Cannot suspend self"})
                continue

            mp.status = "suspended"
            logger.info("Bulk suspend: master id=%s (%s) suspended", mid, mp.user.name)
            results["suspended"].append({
                "master_id": mid,
                "name": mp.user.name
            })
        except HTTPException as e:
            logger.warning("Bulk suspend: master id=%s error: %s", mid, e.detail)
            results["errors"].append({"master_id": mid, "error": e.detail})
        except Exception as e:
            logger.error("Bulk suspend: master id=%s unexpected error: %s", mid, e, exc_info=True)
            results["errors"].append({"master_id": mid, "error": str(e)})

    logger.info(
        "Bulk suspend complete: admin=%s, suspended=%d, errors=%d",
        super_admin.email, len(results["suspended"]), len(results["errors"])
    )
    await db.commit()
    return results


@router.post("/bulk/unsuspend", response_model=dict)
async def bulk_unsuspend(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unsuspend multiple masters at once."""
    logger.info(
        "Bulk unsuspend: admin=%s, masters=%s",
        super_admin.email, master_ids
    )
    results = {"unsuspended": [], "errors": []}

    for mid in master_ids:
        try:
            mp = await _get_master_or_404(db, mid)
            mp.status = "active"
            logger.info("Bulk unsuspend: master id=%s (%s) activated", mid, mp.user.name)
            results["unsuspended"].append({
                "master_id": mid,
                "name": mp.user.name
            })
        except HTTPException as e:
            logger.warning("Bulk unsuspend: master id=%s error: %s", mid, e.detail)
            results["errors"].append({"master_id": mid, "error": e.detail})
        except Exception as e:
            logger.error("Bulk unsuspend: master id=%s unexpected error: %s", mid, e, exc_info=True)
            results["errors"].append({"master_id": mid, "error": str(e)})

    logger.info(
        "Bulk unsuspend complete: admin=%s, unsuspended=%d, errors=%d",
        super_admin.email, len(results["unsuspended"]), len(results["errors"])
    )
    await db.commit()
    return results

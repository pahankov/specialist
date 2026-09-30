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
    results = {"toggled": [], "errors": []}

    for mid in master_ids:
        try:
            mp = await _get_master_or_404(db, mid)
            if mp.user.id == super_admin.id:
                results["errors"].append({"master_id": mid, "error": "Cannot toggle self"})
                continue

            mp.status = "inactive" if mp.status == "active" else "active"
            results["toggled"].append({
                "master_id": mid,
                "name": mp.user.name,
                "new_status": mp.status
            })
        except HTTPException as e:
            results["errors"].append({"master_id": mid, "error": e.detail})
        except Exception as e:
            results["errors"].append({"master_id": mid, "error": str(e)})

    await db.commit()
    return results


@router.post("/bulk/suspend", response_model=dict)
async def bulk_suspend(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Suspend multiple masters at once."""
    results = {"suspended": [], "errors": []}

    for mid in master_ids:
        try:
            mp = await _get_master_or_404(db, mid)
            if mp.user.id == super_admin.id:
                results["errors"].append({"master_id": mid, "error": "Cannot suspend self"})
                continue

            mp.status = "suspended"
            results["suspended"].append({
                "master_id": mid,
                "name": mp.user.name
            })
        except HTTPException as e:
            results["errors"].append({"master_id": mid, "error": e.detail})
        except Exception as e:
            results["errors"].append({"master_id": mid, "error": str(e)})

    await db.commit()
    return results


@router.post("/bulk/unsuspend", response_model=dict)
async def bulk_unsuspend(
    master_ids: List[int],
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Unsuspend multiple masters at once."""
    results = {"unsuspended": [], "errors": []}

    for mid in master_ids:
        try:
            mp = await _get_master_or_404(db, mid)
            mp.status = "active"
            results["unsuspended"].append({
                "master_id": mid,
                "name": mp.user.name
            })
        except HTTPException as e:
            results["errors"].append({"master_id": mid, "error": e.detail})
        except Exception as e:
            results["errors"].append({"master_id": mid, "error": str(e)})

    await db.commit()
    return results

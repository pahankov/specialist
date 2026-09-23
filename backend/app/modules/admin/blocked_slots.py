"""Admin blocked slots endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.admin.base import (
    get_db, BlockedSlot, Master, require_master, get_owned_or_404, log_action,
    BlockedSlotCreate, BlockedSlotResponse
)

router = APIRouter()


@router.get("/blocked-slots")
async def get_blocked_slots(
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Get blocked slots for the authenticated master."""
    result = await db.execute(
        select(BlockedSlot).where(BlockedSlot.master_id == master.id)
        .order_by(BlockedSlot.start_dt.desc())
    )
    slots = result.scalars().all()
    return [
        BlockedSlotResponse(
            id=s.id, master_id=s.master_id, start_dt=s.start_dt,
            end_dt=s.end_dt, reason=s.reason, created_at=s.created_at
        ) for s in slots
    ]


@router.post("/blocked-slots", response_model=BlockedSlotResponse, status_code=201)
async def create_blocked_slot(
    data: BlockedSlotCreate,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Block a time slot."""
    if data.start_dt >= data.end_dt:
        raise HTTPException(status_code=422, detail="start_dt must be before end_dt")
    slot = BlockedSlot(
        master_id=master.id, start_dt=data.start_dt, end_dt=data.end_dt, reason=data.reason
    )
    db.add(slot)
    await db.flush()
    await db.refresh(slot)
    await log_action(db, master.id, "create", "blocked_slot", slot.id,
                     details=f"Блокировка: {slot.start_dt} - {slot.end_dt}", level="info")
    await db.commit()
    return slot


@router.delete("/blocked-slots/{slot_id}", status_code=204)
async def delete_blocked_slot(
    slot_id: int,
    master: Master = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete a blocked slot."""
    slot = await get_owned_or_404(db, BlockedSlot, slot_id, master.id)
    await log_action(db, master.id, "delete", "blocked_slot", slot_id, level="warning")
    await db.delete(slot)
    await db.commit()
    return None

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.database import get_db
from app.models.master import Master
from app.schemas.master import MasterResponse

router = APIRouter()

@router.get("/", response_model=List[MasterResponse])
async def get_masters(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Master))
    masters = result.scalars().all()
    return masters

@router.get("/{master_id}", response_model=MasterResponse)
async def get_master(master_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Master not found")
    return master
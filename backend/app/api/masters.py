from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.database import get_db
from app.models.master import Master
from app.schemas.master import MasterCreate, MasterResponse, MasterUpdate
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/", response_model=List[MasterResponse])
async def get_masters(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    result = await db.execute(
        select(Master).offset(offset).limit(limit)
    )
    return result.scalars().all()


@router.get("/{master_id}", response_model=MasterResponse)
async def get_master(master_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Master not found")
    return master


@router.post("/", response_model=MasterResponse, status_code=201)
async def create_master(master: MasterCreate, db: AsyncSession = Depends(get_db)):
    # Check if master already exists
    result = await db.execute(select(Master).where(Master.email == master.email))
    existing_master = result.scalar_one_or_none()
    if existing_master:
        raise HTTPException(
            status_code=400,
            detail="Master with this email already exists"
        )

    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    hashed_password = pwd_context.hash(master.password)

    new_master = Master(
        name=master.name,
        email=master.email,
        hashed_password=hashed_password,
        phone=master.phone,
        telegram_username=master.telegram_username
    )

    db.add(new_master)
    await db.commit()
    await db.refresh(new_master)
    return new_master


@router.patch("/{master_id}", response_model=MasterResponse)
async def update_master(
    master_id: int,
    master_update: MasterUpdate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        raise HTTPException(status_code=404, detail="Master not found")

    for field, value in master_update.model_dump(exclude_unset=True).items():
        if field == "password" and value:
            from passlib.context import CryptContext
            pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
            master.hashed_password = pwd_context.hash(value)
        else:
            setattr(master, field, value)

    await db.commit()
    await db.refresh(master)
    return master


@router.delete("/{master_id}", status_code=200)
async def delete_master(master_id: int, db: AsyncSession = Depends(get_db)):
    logger.info("Удаление мастера: id=%s", master_id)
    result = await db.execute(select(Master).where(Master.id == master_id))
    master = result.scalar_one_or_none()
    if not master:
        logger.warning("Мастер не найден для удаления: id=%s", master_id)
        raise HTTPException(status_code=404, detail="Master not found")

    await db.delete(master)
    await db.commit()
    logger.info("Мастер успешно удалён: id=%s", master_id)
    return {"detail": "Master deleted"}

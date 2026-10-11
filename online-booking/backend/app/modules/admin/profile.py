"""Current panel user profile (names + city for form defaults)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies.auth import require_master
from app.models.city import City
from app.models.user import User
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/profile")
async def get_my_profile(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Own id/name/city — lets panels prefill (e.g. client city = master's)."""
    city_name = None
    if master.city_id:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == master.city_id)
        )).scalar_one_or_none()
    return {
        "id": master.id,
        "name": master.name,
        "city_id": master.city_id,
        "city_name": city_name,
    }


class ProfileUpdate(BaseModel):
    city_id: Optional[int] = None


@router.patch("/profile")
async def update_my_profile(
    data: ProfileUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Set own city (used as default for new clients)."""
    city_name = None
    if data.city_id is not None:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == data.city_id)
        )).scalar_one_or_none()
        if city_name is None:
            raise HTTPException(status_code=404, detail="Город не найден")
        master.city_id = data.city_id
        await db.commit()
        await db.refresh(master)
    logger.info("Profile updated: user=%s city_id=%s", master.id, master.city_id)
    return {
        "id": master.id,
        "name": master.name,
        "city_id": master.city_id,
        "city_name": city_name,
    }

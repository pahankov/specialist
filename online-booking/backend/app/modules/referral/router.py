"""Public referral links and post-login attribution."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user, require_master
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.services.billing import (
    attribute_referral,
    create_referral_click,
    serialize_billing,
)

router = APIRouter()


class AttributeRequest(BaseModel):
    click_token: str = Field(min_length=10, max_length=120)


@router.post("/click/{code}")
@limiter.limit("40/minute")
async def click_referral(
    request: Request,
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Record a link click; the returned token lives for 60 days."""
    result = await create_referral_click(db, code)
    if result is None:
        raise HTTPException(status_code=404, detail="Реферальная ссылка не найдена")
    await db.commit()
    return result


@router.get("/my")
async def my_referral(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    if master.master_profile is None:
        raise HTTPException(status_code=400, detail="Доступно только мастеру")
    billing = await serialize_billing(db, master.master_profile.id)
    if billing is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    await db.commit()
    return {
        "code": billing["referral_code"],
        "link": billing["referral_link"],
        "qualified_count": billing["referral"]["qualified_count"],
        "max_count": billing["referral"]["max_count"],
        "bonus_total": billing["referral"]["bonus_total"],
        "max_amount": billing["referral"]["max_amount"],
        "click_days": billing["referral"]["click_days"],
        "credit_days": billing["referral"]["credit_days"],
        "referrals": billing["referrals"],
    }


@router.post("/attribute")
async def attribute(
    data: AttributeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await attribute_referral(db, user, data.click_token)
    await db.commit()
    return result

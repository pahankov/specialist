"""Login landing preference for masters (1.82.0).

A master with ``prefer_master_cabinet`` goes straight to the master panel
after login instead of the client cabinet. The flag lives on the master
profile, so it survives devices and follows the account. Admins and plain
clients always land by their own rules.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.master_profile import MasterProfile
from app.models.user import User, UserRole


async def master_landing_preference(db: AsyncSession, user: User) -> bool:
    """True when this user is a master who wants the panel as the landing."""
    if user.role != UserRole.MASTER:
        return False
    value: Optional[bool] = (await db.execute(
        select(MasterProfile.prefer_master_cabinet)
        .where(MasterProfile.user_id == user.id)
    )).scalar_one_or_none()
    return bool(value)

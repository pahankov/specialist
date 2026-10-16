"""Client profile helpers (services layer, no router deps).

Canonical home for ClientProfile ensure-logic shared by the client
cabinet, booking flows, and registration paths. `user_id` is UNIQUE,
so hand-rolled unconditional creates risk IntegrityError — always go
through `get_or_create_profile` (modules -> services).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.client_profile import ClientProfile
from app.models.user import User

logger = get_logger(__name__)


async def get_or_create_profile(db: AsyncSession, user: User) -> ClientProfile:
    """ClientProfile for a user row (created on the fly if missing).

    Flush-only (no commit): safe inside larger transactions, callers
    commit when their own unit of work is complete.
    """
    result = await db.execute(
        select(ClientProfile).where(ClientProfile.user_id == user.id)
    )
    profile = result.scalar_one_or_none()
    if profile is None:
        logger.info("Creating missing ClientProfile for user_id=%s", user.id)
        profile = ClientProfile(user_id=user.id)
        db.add(profile)
        await db.flush()
    return profile

"""Support contact endpoint.

Clients and masters can send a message from the sidebar. Each request is
delivered as a normal bell notification to every active superadmin, so the
existing unread counter and inbox page work without a new UI surface.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.logging_config import get_logger
from app.middleware.rate_limit import limiter
from app.models.user import User, UserRole
from app.services.notifications import notify_user

logger = get_logger(__name__)

router = APIRouter()

ROLE_LABELS = {
    UserRole.CLIENT: "клиент",
    UserRole.MASTER: "мастер",
    UserRole.ADMIN: "администратор",
}


class SupportRequest(BaseModel):
    message: str = Field(min_length=10, max_length=2000)
    page: Optional[str] = Field(default=None, max_length=200)


class SupportRequestResult(BaseModel):
    delivered: int


@router.post("/request", response_model=SupportRequestResult)
@limiter.limit("5/minute")
async def create_support_request(
    request: Request,
    data: SupportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deliver a sidebar support message to the superadmin inbox."""
    message = data.message.strip()
    if len(message) < 10:
        raise HTTPException(status_code=400, detail="Опишите вопрос подробнее (минимум 10 символов)")

    admins = list((await db.execute(
        select(User).where(
            User.role == UserRole.ADMIN,
            User.is_active == True,  # noqa: E712
        )
    )).scalars().all())
    if not admins:
        logger.error("Support request without an active superadmin recipient")
        raise HTTPException(status_code=503, detail="Поддержка временно недоступна")

    role_label = ROLE_LABELS.get(user.role, "пользователь")
    lines = [
        "🆘 Обращение в поддержку",
        f"От: {user.name} ({role_label})",
    ]
    if data.page:
        lines.append(f"Раздел: {data.page}")
    lines.extend(["", message])
    text = "\n".join(lines)

    for admin in admins:
        await notify_user(
            db,
            admin.id,
            text,
            sender_id=user.id,
            audience="support",
            link="support",
            kind="support",
        )

    await db.commit()
    logger.info("Support request from user_id=%s delivered=%s", user.id, len(admins))
    return SupportRequestResult(delivered=len(admins))

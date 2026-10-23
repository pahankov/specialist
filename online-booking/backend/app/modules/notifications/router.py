"""Notification delivery settings shared by clients, masters and admins."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.services.audit import log_action
from app.services.notification_settings import (
    PREFERRED_CHANNELS,
    get_or_create_preference,
    settings_payload,
)

router = APIRouter()


class NotificationSettingsUpdate(BaseModel):
    instant_enabled: Optional[bool] = None
    reminders_enabled: Optional[bool] = None
    max_enabled: Optional[bool] = None
    vk_enabled: Optional[bool] = None
    email_enabled: Optional[bool] = None
    preferred_channel: Optional[str] = Field(default=None, max_length=16)
    master_digest_enabled: Optional[bool] = None
    digest_lead_minutes: Optional[int] = Field(default=None, ge=15, le=180)


@router.get("/settings")
async def get_notification_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    payload = await settings_payload(db, user)
    await db.commit()
    return payload


@router.patch("/settings")
async def update_notification_settings(
    data: NotificationSettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if data.preferred_channel is not None:
        value = data.preferred_channel.strip().lower()
        if value not in PREFERRED_CHANNELS:
            raise HTTPException(status_code=400, detail="Неизвестный канал")
    pref = await get_or_create_preference(db, user.id)
    for field in data.model_fields_set:
        value = getattr(data, field)
        if value is not None:
            if field == "preferred_channel":
                value = value.strip().lower()
            setattr(pref, field, value)
    await log_action(db, user.id, "update", "notification_settings", pref.id,
                     "Настройки уведомлений обновлены", level="info")
    payload = await settings_payload(db, user)
    await db.commit()
    return payload

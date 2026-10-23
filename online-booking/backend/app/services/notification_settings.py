"""Notification preferences and channel availability for one user."""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification_preference import NotificationPreference
from app.models.user import User, UserRole
from app.models.user_contact import UserContact

CHANNELS = ("max", "vk", "email")
PREFERRED_CHANNELS = ("auto", *CHANNELS, "bell")


async def get_or_create_preference(
    db: AsyncSession, user_id: int,
) -> NotificationPreference:
    pref = (await db.execute(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user_id)
    )).scalar_one_or_none()
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)
        await db.flush()
    return pref


async def best_email(
    db: AsyncSession, user: User,
) -> Optional[str]:
    contact = (await db.execute(
        select(UserContact)
        .where(
            UserContact.user_id == user.id,
            UserContact.contact_type == "email",
        )
        .order_by(
            UserContact.is_verified.desc(),
            UserContact.is_primary.desc(),
            UserContact.id.asc(),
        )
        .limit(1)
    )).scalar_one_or_none()
    if contact is not None:
        return contact.value
    return (user.email or "").strip() or None


async def channel_availability(
    db: AsyncSession, user: User,
) -> dict:
    email = await best_email(db, user)
    return {
        "max": {
            "bound": bool(user.max_user_id),
            "available": bool(user.max_user_id) and settings.max_enabled,
        },
        "vk": {
            "bound": bool(user.vk_user_id),
            "available": bool(user.vk_user_id) and settings.vk_notify_enabled,
        },
        "email": {
            "bound": bool(email),
            "available": bool(email) and settings.smtp_enabled,
            "value": email,
        },
    }


async def settings_payload(
    db: AsyncSession, user: User,
) -> dict:
    pref = await get_or_create_preference(db, user.id)
    availability = await channel_availability(db, user)
    return {
        "instant_enabled": bool(pref.instant_enabled),
        "reminders_enabled": bool(pref.reminders_enabled),
        "preferred_channel": pref.preferred_channel,
        "master_digest_enabled": bool(pref.master_digest_enabled),
        "digest_lead_minutes": int(pref.digest_lead_minutes or 60),
        "last_login_provider": user.last_login_provider,
        "is_master": user.role == UserRole.MASTER,
        "is_admin": user.role == UserRole.ADMIN,
        "channels": {
            "max": {
                **availability["max"],
                "enabled": bool(pref.max_enabled),
            },
            "vk": {
                **availability["vk"],
                "enabled": bool(pref.vk_enabled),
            },
            "email": {
                **availability["email"],
                "enabled": bool(pref.email_enabled),
            },
        },
    }


def channel_available(user: User, pref: NotificationPreference,
                      channel: str, *, has_email: bool) -> bool:
    if channel == "max":
        return bool(pref.max_enabled) and bool(user.max_user_id) \
            and settings.max_enabled
    if channel == "vk":
        return bool(pref.vk_enabled) and bool(user.vk_user_id) \
            and settings.vk_notify_enabled
    if channel == "email":
        return bool(pref.email_enabled) and has_email and settings.smtp_enabled
    return False


def choose_channel(user: User, pref: NotificationPreference,
                   *, has_email: bool) -> Optional[str]:
    preferred = (pref.preferred_channel or "auto").lower()
    if preferred == "bell":
        return None
    if preferred in CHANNELS:
        return preferred if channel_available(
            user, pref, preferred, has_email=has_email) else None
    order = []
    if user.last_login_provider in CHANNELS:
        order.append(user.last_login_provider)
    order.extend(ch for ch in CHANNELS if ch not in order)
    for channel in order:
        if channel_available(user, pref, channel, has_email=has_email):
            return channel
    return None

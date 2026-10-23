"""External delivery of bell rows: MAX, VK or email."""
import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import AsyncSessionLocal
from app.logging_config import get_logger
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.services.mailer import send_email
from app.services.max_api import MaxBotApi
from app.services.notification_settings import (
    best_email,
    choose_channel,
    get_or_create_preference,
)
from app.services.vk_notify import send_vk_message

logger = get_logger(__name__)

INTERVAL_SECONDS = 15
LOOKBACK = timedelta(days=2)


def _prefix(user: User) -> str:
    if user.role == UserRole.ADMIN:
        return "/super"
    if user.role == UserRole.MASTER:
        return "/admin"
    return "/cabinet"


def _link_url(user: User, link: Optional[str]) -> Optional[str]:
    base = settings.PUBLIC_BASE_URL.rstrip("/")
    if not link:
        return None
    if link.startswith("review:"):
        return f"{base}/cabinet?review={link.split(':', 1)[1]}"
    prefix = _prefix(user)
    is_client = user.role not in (UserRole.MASTER, UserRole.ADMIN)
    if link.startswith("appointments"):
        if is_client:
            return f"{base}/cabinet"
        appointment_id = link.split(":", 1)[1] if ":" in link else ""
        suffix = f"?highlight={appointment_id}" if appointment_id else ""
        return f"{base}{prefix}/appointments{suffix}"
    if link == "billing":
        # Mirrors the in-app bell: billing is master-bound even for dual roles.
        return f"{base}/admin/billing" if is_client else f"{base}{prefix}/billing"
    if link == "reviews":
        return (f"{base}/admin/profile#reviews"
                if user.role == UserRole.MASTER else f"{base}/cabinet")
    if link.startswith("coupons"):
        coupon_id = link.split(":", 1)[1] if ":" in link else ""
        suffix = f"?highlight={coupon_id}" if coupon_id else ""
        return f"{base}/cabinet/coupons{suffix}"
    if link == "notifications" or link == "support":
        return f"{base}{prefix}/notifications"
    return f"{base}{prefix}/notifications"


def _subject(note: Notification) -> str:
    kind = note.kind or ""
    if kind.startswith("appointment_reminder"):
        return "Напоминание о записи · Электронная запись"
    if kind == "master_digest":
        return "Сводка на сегодня · Электронная запись"
    if kind == "visit_feedback":
        return "Как прошёл визит? · Электронная запись"
    if note.audience == "review":
        return "Новая оценка · Электронная запись"
    if note.audience == "billing":
        return "Тариф и оплата · Электронная запись"
    if note.audience == "support":
        return "Поддержка · Электронная запись"
    if note.audience == "booking":
        return "Запись · Электронная запись"
    return "Уведомление · Электронная запись"


def _text_with_link(user: User, note: Notification) -> str:
    text = (note.text or "").strip()
    url = _link_url(user, note.link)
    if url and url not in text:
        text = f"{text}\n\nОткрыть: {url}"
    return text


def _delivery_allowed(note: Notification, pref) -> bool:
    kind = note.kind or ""
    if kind.startswith("appointment_reminder"):
        return bool(pref.reminders_enabled)
    if kind == "master_digest":
        return bool(pref.master_digest_enabled)
    return bool(pref.instant_enabled)


async def deliver_note(
    db: AsyncSession, user: User, note: Notification,
) -> tuple[Optional[str], Optional[str]]:
    pref = await get_or_create_preference(db, user.id)
    if not _delivery_allowed(note, pref):
        return None, None
    email = await best_email(db, user)
    channel = choose_channel(user, pref, has_email=bool(email))
    if channel is None:
        return None, None
    text = _text_with_link(user, note)
    try:
        if channel == "max":
            await MaxBotApi().send_message(user.max_user_id, text)
            return channel, None
        if channel == "vk":
            ok = await send_vk_message(user.vk_user_id, text)
            return channel, None if ok else "vk_delivery_failed"
        if channel == "email" and email:
            ok = await send_email(email, _subject(note), text)
            return channel, None if ok else "email_delivery_failed"
    except Exception as exc:
        logger.warning("Notification delivery failed: user=%s channel=%s error=%s",
                       user.id, channel, exc)
        return channel, str(exc)[:255]
    return None, None


async def run_notification_dispatch_once(session_factory=None) -> int:
    factory = session_factory or AsyncSessionLocal
    now = datetime.now(timezone.utc)
    sent = 0
    async with factory() as db:
        rows = (await db.execute(
            select(Notification, User)
            .join(User, Notification.recipient_id == User.id)
            .where(
                Notification.external_sent_at.is_(None),
                Notification.created_at >= now - LOOKBACK,
                User.is_active == True,  # noqa: E712
            )
            .order_by(Notification.id.asc())
            .limit(200)
        )).all()
        for note, user in rows:
            try:
                channel, error = await deliver_note(db, user, note)
            except Exception as exc:
                channel, error = None, str(exc)[:255]
                logger.warning("Notification dispatch failed: note=%s error=%s",
                               note.id, exc)
            note.external_sent_at = datetime.now(timezone.utc)
            note.external_channel = channel or "none"
            note.external_error = error
            if channel:
                sent += 1
            await db.commit()
    if sent:
        logger.info("External notifications sent: %s", sent)
    return sent


async def notification_dispatch_loop() -> None:
    while True:
        try:
            await run_notification_dispatch_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Notification dispatch sweep failed: %s", exc)
        await asyncio.sleep(INTERVAL_SECONDS)

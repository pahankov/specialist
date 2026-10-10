"""MAX chat-bot auth business logic.

Design notes:
- Reuses the OtpCode table with channel='max' (same TTL/hash rules as SMS).
- `max_user_id IS NOT NULL` on an unused, unexpired code == bot confirmed.
  `is_used` flips only when the site session is issued (/max/status), so a
  replayed code can never mint a second session.
- Trust model: the code proves control of a MAX *account*, NOT of the typed
  phone number (unlike SMS which arrives at the number itself). Therefore new
  users are created with is_verified=False — same as the SMS path — and the
  MAX display name is taken as a convenience default (editable later).
  Registration may legitimately lack email/name: progressive profiling.
"""
import logging
import re
import secrets
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logging_config import get_logger
from app.models.client_profile import ClientProfile
from app.models.otp_code import OtpCode
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.utils.security import hash_otp_code
from app.utils.tokens import create_access_token, create_refresh_token_payload

logger = get_logger(__name__)

CODE_RE = re.compile(r"^\d{6}$")
MAX_CHANNEL = "max"


def _code_ttl_seconds() -> int:
    return settings.SMS_CODE_TTL_SECONDS  # same policy as SMS codes


def _is_expired(otp: OtpCode) -> bool:
    expires_at = otp.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dt_timezone.utc)
    return datetime.now(dt_timezone.utc) > expires_at


async def start_max_auth(phone: str, db: AsyncSession) -> tuple[str, int]:
    """Create a MAX-channel code for the phone. Returns (code, expires_in)."""
    if not settings.max_enabled:
        raise HTTPException(status_code=503, detail="Вход через MAX не настроен")
    code = f"{secrets.randbelow(1_000_000):06d}"
    ttl = _code_ttl_seconds()
    otp = OtpCode(
        phone=phone,
        code_hash=hash_otp_code(code),
        expires_at=datetime.now(dt_timezone.utc) + timedelta(seconds=ttl),
        is_used=False,
        channel=MAX_CHANNEL,
    )
    db.add(otp)
    await db.commit()
    logger.info("MAX auth code issued for %s (ttl=%ss)", phone, ttl)
    return code, ttl


async def _latest_max_code(phone: str, db: AsyncSession) -> Optional[OtpCode]:
    result = await db.execute(
        select(OtpCode)
        .where(OtpCode.phone == phone, OtpCode.channel == MAX_CHANNEL)
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_max_status(phone: str, db: AsyncSession) -> str:
    """Poll state: 'verified' | 'pending' | 'expired'."""
    otp = await _latest_max_code(phone, db)
    if otp is None or otp.is_used or _is_expired(otp):
        return "expired"
    if otp.max_user_id is not None:
        return "verified"
    return "pending"


def parse_update_code(update: dict) -> tuple[Optional[str], Optional[dict]]:
    """Extract (code_text, sender) from a MAX Update. Pure function.

    Returns (None, sender) when the message carries no 6-digit code,
    (None, None) for non-message updates.
    """
    if not isinstance(update, dict):
        return None, None
    if update.get("update_type") != "message_created":
        return None, None
    message = update.get("message") or {}
    body = message.get("body") or {}
    text = (body.get("text") or message.get("text") or "")
    text = text.strip() if isinstance(text, str) else ""
    sender = message.get("sender") or {}
    if not isinstance(sender, dict):
        sender = {}
    if CODE_RE.match(text):
        return text, sender
    return None, sender


def sender_display_name(sender: dict) -> str:
    parts = [sender.get("first_name") or "", sender.get("last_name") or ""]
    name = " ".join(p for p in parts if p).strip()
    return name


async def confirm_max_code(
    db: AsyncSession, sender_id: int, sender_name: str, text: str
) -> str:
    """Match an inbound bot code to a pending MAX code.

    Returns 'confirmed' | 'unknown' | 'expired' | 'already'.
    """
    code_hash = hash_otp_code(text)
    result = await db.execute(
        select(OtpCode)
        .where(
            OtpCode.channel == MAX_CHANNEL,
            OtpCode.code_hash == code_hash,
            OtpCode.is_used == False,  # noqa: E712
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()
    if otp is None:
        # Either a wrong code or an already-consumed one.
        used = await db.execute(
            select(func.count(OtpCode.id)).where(
                OtpCode.channel == MAX_CHANNEL,
                OtpCode.code_hash == code_hash,
                OtpCode.is_used == True,  # noqa: E712
            )
        )
        if (used.scalar() or 0) > 0:
            return "already"
        return "unknown"
    if _is_expired(otp):
        return "expired"
    if otp.max_user_id is not None:
        return "already"
    otp.max_user_id = sender_id
    otp.max_user_name = sender_name[:200] if sender_name else None
    await db.commit()
    logger.info(
        "MAX code confirmed: otp_id=%s phone=%s max_user_id=%s",
        otp.id, otp.phone, sender_id,
    )
    return "confirmed"


async def complete_max_session(
    phone: str, db: AsyncSession
) -> tuple[str, User, bool]:
    """Issue JWT session for a bot-verified phone. Returns (token, user, is_new)."""
    otp = await _latest_max_code(phone, db)
    if otp is None or otp.is_used or _is_expired(otp) or otp.max_user_id is None:
        raise HTTPException(status_code=400, detail="Код не подтверждён в MAX")

    otp.is_used = True
    await db.commit()

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    is_new = False
    if not user:
        is_new = True
        fallback_name = (otp.max_user_name or "").strip()
        logger.info("Creating new client via MAX: phone=%s", phone)
        user = User(
            name=fallback_name,  # MAX display name; editable later
            phone=phone,
            role=UserRole.CLIENT,
            hashed_password=None,  # MAX-only auth (same as OTP path)
            is_verified=False,  # MAX proves account control, not the number
        )
        db.add(user)
        await db.flush()
        db.add(ClientProfile(user_id=user.id))
        await db.commit()
        await db.refresh(user)
        logger.info("New client created via MAX: user_id=%s", user.id)

    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "is_admin": user.role == UserRole.ADMIN,
    })
    refresh_value, expires_at = create_refresh_token_payload(user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_value, expires_at=expires_at))
    await db.commit()

    logger.info("Client logged in via MAX: user_id=%s is_new=%s", user.id, is_new)
    return access_token, user, is_new


async def get_latest_refresh_token_value(db: AsyncSession, user_id: int) -> Optional[str]:
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False)  # noqa: E712
        .order_by(RefreshToken.id.desc())
        .limit(1)
    )
    stored = result.scalar_one_or_none()
    return stored.token if stored else None

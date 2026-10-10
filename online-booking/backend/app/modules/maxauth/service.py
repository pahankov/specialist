"""MAX chat-bot auth business logic (SMS-style flow).

Flow: site takes the phone -> backend stores a pending MAX code (NEVER shown
on site) -> user opens the bot and shares their number (typed text or the
`request_contact` button) -> bot replies INTO the dialog with the code ->
user types it on site -> /max/verify mints the JWT session.

Trust model (see https://dev.max.ru, request_contact section):
- Phone from a `request_contact` attachment whose HMAC-SHA256(access_token,
  vcf_info) matches `hash` is PROVEN to be the sender's MAX-bound number
  -> created users get is_verified=True.
- Typed phone text is self-asserted (anyone can type anyone's number) ->
  is_verified=False, same as the SMS path; TTL 5 min + 10/min rate limit
  bound the guessing window.
- Registration may legitimately lack email/name: the MAX display name is a
  convenience default, the rest is progressive profiling.
"""
import hashlib
import hmac
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
from app.utils.phone import normalize_phone
from app.utils.security import hash_otp_code
from app.utils.tokens import create_access_token, create_refresh_token_payload

logger = get_logger(__name__)

MAX_CHANNEL = "max"


def _code_ttl_seconds() -> int:
    return settings.SMS_CODE_TTL_SECONDS  # same policy as SMS codes


def _is_expired(otp: OtpCode) -> bool:
    expires_at = otp.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=dt_timezone.utc)
    return datetime.now(dt_timezone.utc) > expires_at


async def start_max_auth(phone: str, db: AsyncSession) -> int:
    """Store a pending MAX code for the phone. Returns ttl seconds.

    The code itself is NEVER returned to the site — the bot delivers it
    into the MAX dialog after the user shares their number there.
    """
    if not settings.max_enabled:
        raise HTTPException(status_code=503, detail="Вход через MAX не настроен")
    code = f"{secrets.randbelow(1_000_000):06d}"
    ttl = _code_ttl_seconds()
    db.add(OtpCode(
        phone=phone,
        code_hash=hash_otp_code(code),
        expires_at=datetime.now(dt_timezone.utc) + timedelta(seconds=ttl),
        is_used=False,
        channel=MAX_CHANNEL,
    ))
    await db.commit()
    logger.info("MAX auth requested for %s (ttl=%ss)", phone, ttl)
    return ttl


async def _latest_pending_code(phone: str, db: AsyncSession) -> Optional[OtpCode]:
    result = await db.execute(
        select(OtpCode)
        .where(
            OtpCode.phone == phone,
            OtpCode.channel == MAX_CHANNEL,
            OtpCode.is_used == False,  # noqa: E712
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()
    if otp is not None and _is_expired(otp):
        return None
    return otp


def sender_display_name(sender: dict) -> str:
    """MAX display name from a sender object (first + last)."""
    parts = [(sender or {}).get("first_name") or "",
             (sender or {}).get("last_name") or ""]
    return " ".join(p for p in parts if p).strip()


def parse_phone_text(text: str) -> Optional[str]:
    """Normalize free-typed text to a phone, or None if it is not a phone."""
    digits = re.sub(r"\D", "", text or "")
    if len(digits) not in (10, 11):
        return None
    try:
        return normalize_phone(digits)
    except ValueError:
        return None


def parse_contact_phone(message: dict) -> tuple[Optional[str], bool, str]:
    """Extract (phone, hmac_verified, display_name) from a contact attachment.

    Returns (None, False, name) when there is no contact attachment.
    HMAC check per MAX docs: HMAC-SHA256(access_token, vcf_info) == hash.
    """
    body = (message or {}).get("body") or {}
    sender = (message or {}).get("sender") or {}
    name_parts = [sender.get("first_name") or "", sender.get("last_name") or ""]
    display = " ".join(p for p in name_parts if p).strip()
    attachments = body.get("attachments") or []
    for att in attachments:
        if not isinstance(att, dict) or att.get("type") != "contact":
            continue
        payload = att.get("payload") or {}
        vcf = payload.get("vcf_info") or ""
        digest = payload.get("hash") or ""
        m = re.search(r"TEL[^:]*:(\+?\d+)", vcf)
        if not m:
            continue
        phone = parse_phone_text(m.group(1))
        if phone is None:
            continue
        if not settings.MAX_BOT_TOKEN or not digest:
            return phone, False, display
        expect = hmac.new(
            settings.MAX_BOT_TOKEN.encode(), vcf.encode(), hashlib.sha256
        ).hexdigest()
        return phone, hmac.compare_digest(expect, digest), display
    return None, False, display


async def deliver_code_to_dialog(
    db: AsyncSession,
    phone: str,
    sender_id: int,
    sender_name: str,
    phone_verified: bool,
) -> Optional[str]:
    """Mint a fresh dialog code for the pending request. Returns plain code.

    The site-pending code value is never stored (only its hash), so delivery
    generates a NEW code, swaps the hash on the same row (TTL preserved) and
    returns the plain text for the bot reply. None when no pending request
    exists — the caller must ask the user to request a code on site first.
    """
    otp = await _latest_pending_code(phone, db)
    if otp is None:
        return None
    code = f"{secrets.randbelow(1_000_000):06d}"
    otp.code_hash = hash_otp_code(code)
    otp.max_user_id = sender_id
    otp.max_user_name = (sender_name[:200] if sender_name else None)
    otp.max_verified_phone = bool(phone_verified)
    await db.commit()
    logger.info(
        "MAX code delivered to dialog: otp_id=%s phone=%s verified=%s",
        otp.id, phone, phone_verified,
    )
    return code


async def verify_max_code(
    phone: str, code: str, db: AsyncSession
) -> tuple[str, User, bool]:
    """Check a site-typed MAX code, mint the JWT session. Returns (token, user, is_new)."""
    code_hash = hash_otp_code(code)
    result = await db.execute(
        select(OtpCode)
        .where(
            OtpCode.phone == phone,
            OtpCode.channel == MAX_CHANNEL,
            OtpCode.code_hash == code_hash,
            OtpCode.is_used == False,  # noqa: E712
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )
    otp = result.scalar_one_or_none()
    if otp is None:
        raise HTTPException(status_code=400, detail="Неверный код")
    if _is_expired(otp):
        raise HTTPException(status_code=410, detail="Код истёк. Запросите новый.")
    if otp.max_user_id is None:
        raise HTTPException(
            status_code=400,
            detail="Сначала получите код от бота в MAX",
        )

    otp.is_used = True
    await db.commit()

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    is_new = False
    if not user:
        is_new = True
        logger.info("Creating new client via MAX: phone=%s", phone)
        user = User(
            name=(otp.max_user_name or "").strip(),
            phone=phone,
            role=UserRole.CLIENT,
            hashed_password=None,  # MAX-only auth (same as OTP path)
            # Verified only when the number came from a contact share
            # whose HMAC matched (proven MAX-bound number).
            is_verified=bool(otp.max_verified_phone),
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

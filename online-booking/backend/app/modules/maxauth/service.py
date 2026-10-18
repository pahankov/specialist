"""MAX chat-bot auth business logic (SMS-style flow).

Flow: site takes the phone -> backend stores a pending MAX code (NEVER shown
on site) -> user opens the bot and shares their number (typed text or the
`request_contact` button) -> bot replies INTO the dialog with the code ->
user types it on site -> /max/verify mints the JWT session.

An HMAC-proven contact share may also OPEN the request itself (no site step
beforehand): deliver_code_to_dialog() creates the pending row on the fly,
so "open bot -> share number -> code -> type code on site" registers the
account without typing the phone on site first.

Trust model (see https://dev.max.ru, request_contact section):
- Phone from a `request_contact` attachment whose HMAC-SHA256(access_token,
  vcf_info) matches `hash` is PROVEN to be the sender's MAX-bound number
  -> created users get is_verified=True; the same proof upgrades
  is_verified for existing accounts at /max/verify.
- Typed phone text is self-asserted (anyone can type anyone's number) ->
  is_verified=False, same as the SMS path; TTL 5 min + 10/min rate limit
  bound the guessing window. Never opens a request on its own.
- 152-FZ consent is captured on site at /max/verify (checkbox on the login
  form), stamped on user creation/backfill exactly like register-unified.
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
from app.services.names import name_fields, split_full_name
from app.services.social_merge import merge_social_profile
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


async def start_max_auth(phone: str, db: AsyncSession) -> tuple[int, int]:
    """Store a pending MAX code for the phone. Returns (otp_id, ttl).

    The code itself is NEVER returned to the site. Delivery paths:
    bound dialog (push), deeplink open with payload (auto-meet), or
    share-number flow — all converge on deliver_code_to_dialog().
    """
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
    await db.flush()
    otp_id = otp.id
    await db.commit()
    logger.info("MAX auth requested for %s (ttl=%ss)", phone, ttl)
    return otp_id, ttl


def _payload_key() -> bytes:
    """Server-side HMAC key for deeplink payloads (never leaves backend)."""
    return (settings.MAX_WEBHOOK_SECRET or settings.MAX_BOT_TOKEN).encode()


def make_start_payload(otp_id: int) -> str:
    """Tamper-proof deeplink payload binding a dialog open to a request.

    Format `<otp_id>_<hmac32>` — fits the bot payload charset [a-z0-9_-].
    """
    mac = hmac.new(_payload_key(), str(otp_id).encode(), hashlib.sha256)
    return f"{otp_id}_{mac.hexdigest()[:32]}"


def parse_start_payload(payload: str) -> Optional[int]:
    """Validate a deeplink payload. Returns otp_id or None."""
    try:
        raw_id, mac = (payload or "").split("_", 1)
        otp_id = int(raw_id)
    except (ValueError, AttributeError):
        return None
    expect = hmac.new(_payload_key(), str(otp_id).encode(), hashlib.sha256)
    if not hmac.compare_digest(expect.hexdigest()[:32], mac):
        return None
    return otp_id


def make_start_deeplink(otp_id: int) -> str:
    """Full one-click bot URL carrying the request payload ("" if unconfigured)."""
    username = settings.MAX_BOT_USERNAME
    if not username:
        return ""
    return f"https://max.ru/{username}?start={make_start_payload(otp_id)}"


def build_code_message(code: str) -> tuple[str, list]:
    """Bot text + clipboard button for a login code (shared by push/webhook)."""
    text = (f"Ваш код для входа: {code}\n"
            "Введите его на сайте. Никому не сообщайте.")
    attachments = [{
        "type": "inline_keyboard",
        "payload": {"buttons": [[
            {"type": "clipboard", "text": "Скопировать код",
             "payload": code},
        ]]},
    }]
    return text, attachments


async def prepare_push_code(phone: str, db: AsyncSession) -> Optional[tuple[int, str]]:
    """Mint a dialog code for a BOUND user. Returns (max_user_id, code).

    None when the phone has no bound MAX account (or no pending request) —
    the caller falls back to the share-number flow. The hash on the pending
    row is swapped (TTL preserved); plain code exists only in the reply.
    """
    result = await db.execute(
        select(User).where(
            User.phone == phone,
            User.max_user_id.is_not(None),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        return None
    otp = await _latest_pending_code(phone, db)
    if otp is None:
        return None
    code = f"{secrets.randbelow(1_000_000):06d}"
    otp.code_hash = hash_otp_code(code)
    otp.max_user_id = user.max_user_id
    otp.max_user_name = user.name[:200] if user.name else None
    otp.max_verified_phone = bool(user.is_verified)
    await db.commit()
    logger.info("MAX code prepared for push: otp_id=%s phone=%s", otp.id, phone)
    return user.max_user_id, code


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


async def get_pending_otp(otp_id: int, db: AsyncSession) -> Optional[OtpCode]:
    """Load a MAX request by id if still pending (unused, unexpired)."""
    result = await db.execute(
        select(OtpCode).where(
            OtpCode.id == otp_id,
            OtpCode.channel == MAX_CHANNEL,
            OtpCode.is_used == False,  # noqa: E712
        )
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


def parse_contact_phone(
    message: dict,
) -> tuple[Optional[str], bool, str, Optional[str]]:
    """Extract (phone, hmac_verified, display_name, email) from a contact.

    Returns (None, False, name, None) when there is no contact attachment.
    HMAC check per MAX docs: HMAC-SHA256(access_token, vcf_info) == hash.
    The email is taken from the vCard when present (self-reported profile
    data — useful, but NOT platform-verified like the phone).
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
        email = parse_vcf_email(vcf)
        if not settings.MAX_BOT_TOKEN or not digest:
            return phone, False, display, email
        expect = hmac.new(
            settings.MAX_BOT_TOKEN.encode(), vcf.encode(), hashlib.sha256
        ).hexdigest()
        return phone, hmac.compare_digest(expect, digest), display, email
    return None, False, display, None


def parse_vcf_email(vcf: str) -> Optional[str]:
    """Email from a contact vCard, or None (absent/obviously malformed)."""
    m = re.search(r"EMAIL[^:]*:([^\s\r\n]+)", vcf or "", re.IGNORECASE)
    if not m:
        return None
    email = m.group(1).strip().strip('"').lower()
    # Cheap sanity: local@domain.tld, no spaces (vCard lines are newline-split).
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[a-zа-я]{2,}", email):
        return None
    return email


def sender_username(sender: dict) -> Optional[str]:
    """MAX public nickname (@username), None when absent."""
    return (sender or {}).get("username") or None



async def deliver_code_to_dialog(
    db: AsyncSession,
    phone: str,
    sender_id: int,
    sender_name: str,
    phone_verified: bool,
    username: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[str]:
    """Mint a fresh dialog code for the pending request. Returns plain code.

    The site-pending code value is never stored (only its hash), so delivery
    generates a NEW code, swaps the hash on the same row (TTL preserved) and
    returns the plain text for the bot reply.

    None only for a typed phone with no site request: self-asserted numbers
    must not open requests (anyone could type anyone's number). An HMAC-
    proven contact share MAY open the request itself — the platform vouches
    the number belongs to this MAX account, so "share number" alone is a
    valid registration start.
    """
    otp = await _latest_pending_code(phone, db)
    code = f"{secrets.randbelow(1_000_000):06d}"
    if otp is None:
        if not phone_verified:
            return None
        ttl = _code_ttl_seconds()
        otp = OtpCode(
            phone=phone,
            code_hash=hash_otp_code(code),
            expires_at=datetime.now(dt_timezone.utc) + timedelta(seconds=ttl),
            is_used=False,
            channel=MAX_CHANNEL,
            max_user_id=sender_id,
            max_user_name=(sender_name[:200] if sender_name else None),
            max_verified_phone=True,
            max_username=(username[:64] if username else None),
            max_user_email=email,
        )
        db.add(otp)
        await db.commit()
        logger.info(
            "MAX contact share opened the request: phone=%s (ttl=%ss)",
            phone, ttl,
        )
        return code
    otp.code_hash = hash_otp_code(code)
    otp.max_user_id = sender_id
    otp.max_user_name = (sender_name[:200] if sender_name else None)
    otp.max_verified_phone = bool(phone_verified)
    if username:
        otp.max_username = username[:64]
    if email:
        otp.max_user_email = email
    await db.commit()
    logger.info(
        "MAX code delivered to dialog: otp_id=%s phone=%s verified=%s",
        otp.id, phone, phone_verified,
    )
    return code


async def verify_max_code(
    phone: str, code: str, db: AsyncSession, consent: bool = False
) -> tuple[str, User, bool]:
    """Check a site-typed MAX code, mint the JWT session. Returns (token, user, is_new).

    `consent` is the 152-FZ checkbox state from the site form: stamped on
    new accounts and backfilled onto legacy MAX/OTP accounts (NULL consent)
    that log in through the consented form.
    """
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

    from app.modules.auth.service import OFFER_VERSION, POLICY_VERSION

    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    is_new = False
    if not user:
        is_new = True
        logger.info("Creating new client via MAX: phone=%s", phone)
        max_name, max_last = name_fields(otp.max_user_name)
        # Email from the contact vCard is self-reported profile data: take it
        # only when it does not collide with an existing account.
        email = otp.max_user_email
        if email:
            taken = (await db.execute(
                select(User.id).where(User.email == email)
            )).scalar_one_or_none()
            if taken is not None:
                logger.info("MAX vCard email already taken, skipping: %s", email)
                email = None
        user = User(
            name=max_name,
            last_name=max_last,
            phone=phone,
            email=email,
            role=UserRole.CLIENT,
            hashed_password=None,  # MAX-only auth (same as OTP path)
            # Verified only when the number came from a contact share
            # whose HMAC matched (proven MAX-bound number).
            is_verified=bool(otp.max_verified_phone),
            max_user_id=otp.max_user_id,  # bind account for push-code login
            max_username=otp.max_username,  # @nickname for support/UX
            # name came from MAX's display name: a later social login may
            # refresh it; a human edit ("user") will not be overwritten.
            name_source=("max" if max_name else None),
            # 152-FZ: same consent stamp as register-unified, taken from
            # the checkbox on the MAX login form.
            consent_at=(
                datetime.now(dt_timezone.utc) if consent else None),
            consent_policy_version=POLICY_VERSION if consent else None,
            consent_offer_version=OFFER_VERSION if consent else None,
        )
        db.add(user)
        await db.flush()
        from app.services.clients import get_or_create_profile
        await get_or_create_profile(db, user)
        await db.commit()
        await db.refresh(user)
        logger.info("New client created via MAX: user_id=%s", user.id)
    else:
        changed = False
        if user.max_user_id is None and otp.max_user_id is not None:
            # Link a pre-existing account (e.g. password-registered master)
            # to the MAX account that just proved the number.
            user.max_user_id = otp.max_user_id
            changed = True
            logger.info("Linked MAX account to user_id=%s", user.id)
        if user.max_username is None and otp.max_username:
            user.max_username = otp.max_username
            changed = True
        # Smart merge: name from MAX's display name, fill a missing email, only
        # ever raise is_verified (the HMAC-proven number) — a human-set
        # name/email is never overwritten.
        max_first, max_last_name = split_full_name(otp.max_user_name or "")
        merged = await merge_social_profile(
            db, user, provider="max",
            first_name=max_first, last_name=max_last_name,
            email=otp.max_user_email,
            avatar_url=None,  # MAX carries no avatar
            verified=bool(otp.max_verified_phone),
        )
        changed = changed or merged
        if consent and user.consent_at is None:
            # Backfill consent for accounts created before consent tracking.
            user.consent_at = datetime.now(dt_timezone.utc)
            user.consent_policy_version = POLICY_VERSION
            user.consent_offer_version = OFFER_VERSION
            changed = True
        if changed:
            await db.commit()

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

"""MAX chat-bot auth business logic (SMS-style flow).

Flow: site takes the phone -> backend stores a pending MAX code (NEVER shown
on site) -> the user opens the bot and shares their number with the
`request_contact` button -> bot replies INTO the dialog with the code ->
user types it on site -> /max/verify mints the JWT session.

An HMAC-proven contact share may also OPEN the request itself (no site step
beforehand): deliver_code_to_dialog() creates the pending row on the fly,
so "open bot -> share number -> code -> type code on site" registers the
account without typing the phone on site first.

Trust model (see https://dev.max.ru, request_contact section):
- The code reaches a dialog ONLY for a PROVEN number: `request_contact`
  attachment whose HMAC-SHA256(access_token, vcf_info) matches `hash` is
  platform-vouched to be the sender's number -> the phone contact is
  created/upgraded as verified-by-social at /max/verify.
- Opening a deeplink (?start=...) or typing a number/text in the dialog
  proves NOTHING about number ownership (anyone can type anyone's number):
  those paths only ever get the share-number keyboard, never a code. The
  pre-1.78.3 "auto-meet" deeplink delivery was an account-takeover hole.
- The one exception is push_code: the code goes into a dialog ALREADY bound
  to the account by an earlier verified share (User.max_user_id).
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
from app.models.otp_code import OtpCode
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.names import split_full_name
from app.services.social_merge import complete_social_login, resolve_social_user
from app.utils.phone import normalize_phone
from app.utils.security import hash_otp_code

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

    The code itself is NEVER returned to the site. Delivery paths: push into
    a bound dialog, or an HMAC-verified contact share in the dialog — both
    converge on deliver_code_to_dialog().
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


# Callback payload of the «Начать заново» button under the code message.
RESTART_CALLBACK = "restart"


def build_code_message(code: str) -> tuple[str, list]:
    """Bot text + buttons for a login code (shared by push/webhook).

    MAX hides the one-time request_contact keyboard after the first share,
    which dead-ends a re-opened dialog. The callback button below re-issues
    that keyboard on demand (see the webhook message_callback branch).
    """
    text = (f"Ваш код для входа: {code}\n"
            "Введите его на сайте. Никому не сообщайте.")
    attachments = [{
        "type": "inline_keyboard",
        "payload": {"buttons": [
            [{"type": "clipboard", "text": "Скопировать код",
              "payload": code}],
            [{"type": "callback", "text": "🔄 Начать заново",
              "payload": RESTART_CALLBACK}],
        ]},
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
    # The bound dialog was proven with an HMAC-verified share earlier, so
    # the number is platform-vouched for this delivery too.
    otp.max_verified_phone = True
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
    display = sender_display_name(sender)
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
    """Mint a fresh dialog code for a VERIFIED contact share. Returns code.

    The site-pending code value is never stored (only its hash), so delivery
    generates a NEW code, swaps the hash on the same row (TTL preserved) and
    returns the plain text for the bot reply.

    An HMAC-proven contact share MAY also open the request itself — the
    platform vouches the number belongs to this MAX account, so "share
    number" alone is a valid registration start.

    Returns None only for an unverified number (guard): the router never
    calls this for typed text, but nothing self-asserted may mint a code.
    """
    if not phone_verified:
        return None
    otp = await _latest_pending_code(phone, db)
    code = f"{secrets.randbelow(1_000_000):06d}"
    if otp is None:
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
        # The typed phone may not be the number whose contact was shared in
        # the bot («Поделиться номером» sends the MAX account's own number).
        # A code that matches ANOTHER delivered request gets a pointed hint
        # instead of a flat «Неверный код» — still no session out of it.
        other = (await db.execute(
            select(OtpCode)
            .where(
                OtpCode.channel == MAX_CHANNEL,
                OtpCode.code_hash == code_hash,
                OtpCode.is_used == False,  # noqa: E712
                OtpCode.max_user_id.is_not(None),
            )
            .order_by(OtpCode.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
        if other is not None and not _is_expired(other):
            logger.info(
                "MAX verify: code delivered for another number (typed=%s, code_for=%s)",
                phone, other.phone,
            )
            raise HTTPException(
                status_code=400,
                detail=(f"Код отправлен для номера {other.phone} — "
                        "введите этот номер в поле выше и войдите снова."),
            )
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

    # One shared resolution for every social login («Единый вход»): the MAX
    # user id bound to the sender first, then the HMAC-proven phone, then
    # create; contacts land on the account through the contact service.
    # The vCard email is self-reported: attached unverified, skipped when
    # another account holds it, never a lookup key.
    max_first, max_last_name = split_full_name(otp.max_user_name or "")
    user, is_new = await resolve_social_user(
        db,
        provider="max",
        social_id=otp.max_user_id,
        social_field="max_user_id",
        link_fields={"max_username": otp.max_username},
        first_name=max_first,
        last_name=max_last_name,
        phone=phone,
        phone_confirmed=bool(otp.max_verified_phone),
        email=otp.max_user_email,
        email_confirmed=False,
        avatar_url=None,  # MAX carries no avatar
        consent=consent,
        defer_creation=(not consent),
    )
    # No consent and none stamped yet (new OR abandoned pending account):
    # return a challenge instead of a session — the frontend shows the
    # ConsentScreen, then /auth/consent/complete stamps consent + logs in.
    if not consent and user.consent_at is None:
        from app.modules.auth.service import _create_challenge_token
        challenge = _create_challenge_token(user.id, phone or "")
        return challenge, user, is_new
    access_token = await complete_social_login(db, user)
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

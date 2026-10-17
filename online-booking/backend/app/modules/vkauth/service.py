"""VK ID auth business logic (OAuth 2.0 Authorization Code Flow + PKCE).

Flow: site calls /vk/start (gets a signed state + authorize URL) -> the
browser is redirected to id.vk.ru/authorize -> the user approves there ->
VK redirects back to the frontend callback with `code` + `device_id` +
`state` -> the frontend posts those (plus the PKCE code_verifier it kept)
to /vk/verify -> backend trades the code for an access token, reads the
profile, creates/binds the account and mints the JWT session.

Why this shape (VK's docs, dev.vk.ru):
- PKCE is mandatory: the code_verifier is generated in the browser, only
  its SHA256 (code_challenge) goes to VK, and the verifier is presented at
  the token exchange. A stolen code is useless without the verifier.
- The code is exchanged SERVER-SIDE (recommended scheme): access/refresh/id
  tokens never touch the browser, only our backend.
- `state` is signed by us (HMAC + 10 min TTL) and echoed back unchanged, so
  a callback with a foreign/forged state is rejected before any token call.
- Registration and login are one flow: the account is created on the first
  successful exchange (matched by vk_user_id thereafter).
- 152-FZ consent is captured on the site form (checkbox) and passed into
  /vk/verify — stamped on new accounts, backfilled onto legacy ones.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.logging_config import get_logger
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.services.names import compose_full_name
from app.services.vk_api import VkApiError, get_vk_api
from app.utils.tokens import create_access_token, create_refresh_token_payload

logger = get_logger(__name__)

# How long an authorize round-trip may take before the state is stale.
STATE_TTL_SECONDS = 600


def _state_key() -> bytes:
    """Server-side HMAC key for VK states (never leaves the backend)."""
    return settings.SECRET_KEY.encode()


def make_state() -> str:
    """Tamper-proof state binding a callback to an authorize start.

    Format `<ts>_<nonce>_<hmac32>` — carries its own issued-at so /vk/verify
    can reject stale callbacks without a DB round-trip.
    """
    ts = str(int(datetime.now(dt_timezone.utc).timestamp()))
    # Hex nonce: never contains the "_" delimiter, so the state can always
    # be split back into exactly (ts, nonce, mac) on parse.
    nonce = secrets.token_hex(8)
    mac = hmac.new(_state_key(), f"{ts}_{nonce}".encode(), hashlib.sha256)
    return f"{ts}_{nonce}_{mac.hexdigest()[:32]}"


def parse_state(state: str) -> bool:
    """True when the state was minted by us and is still fresh."""
    try:
        ts_raw, nonce, mac = (state or "").split("_", 2)
        issued_at = int(ts_raw)
    except (ValueError, AttributeError):
        return False
    expect = hmac.new(
        _state_key(), f"{ts_raw}_{nonce}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    if not hmac.compare_digest(expect, mac):
        return False
    age = datetime.now(dt_timezone.utc).timestamp() - issued_at
    return 0 <= age <= STATE_TTL_SECONDS


# VK consent screen (server-side constant — not a secret, just the entry URL).
VK_AUTHORIZE_URL = "https://id.vk.ru/authorize"


def build_authorize_url(state: str, code_challenge: str) -> str:
    """Full VK consent URL: PKCE challenge + signed state baked in."""
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": settings.VK_CLIENT_ID,
        "redirect_uri": settings.VK_REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    scope = (settings.VK_SCOPE or "").strip()
    if scope:
        params["scope"] = scope
    return f"{VK_AUTHORIZE_URL}?{urlencode(params)}"


async def verify_vk_code(
    code: str,
    device_id: str,
    state: str,
    code_verifier: str,
    db: AsyncSession,
    consent: bool = False,
) -> tuple[str, User, bool]:
    """Exchange the VK code, create/bind the account, mint the JWT.

    Returns (token, user, is_new). Raises 4xx on a bad state, a rejected
    exchange, or a profile read failure — never logs anyone in blind.
    """
    if not settings.vk_enabled:
        raise HTTPException(status_code=503, detail="Вход через VK не настроен")
    if not parse_state(state):
        raise HTTPException(
            status_code=400,
            detail="Неверная или просроченная сессия входа. Попробуйте снова.",
        )

    api = get_vk_api()
    try:
        tokens = await api.exchange_code(code, code_verifier, device_id, state)
        profile = await api.user_info(tokens["access_token"])
    except VkApiError as e:
        logger.warning("VK ID exchange failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Не удалось войти через VK. Попробуйте позже.",
        )

    vk_user = (profile or {}).get("user") or {}
    vk_user_id = vk_user.get("user_id") or tokens.get("user_id")
    if vk_user_id is None:
        raise HTTPException(
            status_code=400, detail="VK не вернул идентификатор пользователя")
    vk_user_id = int(vk_user_id)

    first = (vk_user.get("first_name") or "").strip()
    last = (vk_user.get("last_name") or "").strip()
    email = _clean_email(vk_user.get("email"))

    from app.modules.auth.service import OFFER_VERSION, POLICY_VERSION

    result = await db.execute(
        select(User).where(User.vk_user_id == vk_user_id))
    user = result.scalar_one_or_none()
    is_new = False

    if user is None and email:
        # A pre-existing account with the same email: link it to VK instead of
        # creating a duplicate (same progressive-profiling rule as MAX).
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None:
            user.vk_user_id = vk_user_id
            logger.info("Linked VK account to existing user_id=%s", user.id)

    if user is None:
        is_new = True
        logger.info("Creating new client via VK: vk_user_id=%s", vk_user_id)
        user = User(
            name=compose_full_name(first, last) or "VK Пользователь",
            last_name=last or None,
            email=email,
            phone=None,  # phone only arrives with the extended scope
            role=UserRole.CLIENT,
            hashed_password=None,  # VK-only auth (same as OTP/MAX paths)
            # VK vouches the account, so the profile is trusted; the grey
            # "verified" tick further confirms the personal data.
            is_verified=bool(vk_user.get("verified")),
            vk_user_id=vk_user_id,
            # 152-FZ: consent checkbox on the VK login form.
            consent_at=(datetime.now(dt_timezone.utc) if consent else None),
            consent_policy_version=POLICY_VERSION if consent else None,
            consent_offer_version=OFFER_VERSION if consent else None,
        )
        db.add(user)
        await db.flush()
        from app.services.clients import get_or_create_profile
        await get_or_create_profile(db, user)
        logger.info("New client created via VK: user_id=%s", user.id)
    else:
        changed = False
        if user.is_active is False:
            raise HTTPException(
                status_code=403, detail="Аккаунт заблокирован.")
        if email and user.email is None:
            user.email = email
            changed = True
        if not user.name and (first or last):
            user.name = compose_full_name(first, last)
            user.last_name = last or None
            changed = True
        if consent and user.consent_at is None:
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
    refresh_value, expires_at = create_refresh_token_payload(
        user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_value,
                        expires_at=expires_at))
    await db.commit()

    logger.info("User logged in via VK: user_id=%s is_new=%s", user.id, is_new)
    return access_token, user, is_new


def _clean_email(raw: Optional[str]) -> Optional[str]:
    """Lowercase/validate an email from the VK profile, or None."""
    if not raw:
        return None
    email = str(raw).strip().strip('"').lower()
    if not email or "@" not in email or " " in email:
        return None
    return email


async def get_latest_refresh_token_value(
    db: AsyncSession, user_id: int
) -> Optional[str]:
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.user_id == user_id,
               RefreshToken.is_revoked == False)  # noqa: E712
        .order_by(RefreshToken.id.desc())
        .limit(1)
    )
    stored = result.scalar_one_or_none()
    return stored.token if stored else None

"""Yandex ID auth business logic (OAuth 2.0 Authorization Code Flow).

Flow: site calls /yandex/start (gets a signed state + authorize URL) -> the
browser is redirected to oauth.yandex.ru/authorize -> the user approves there
-> Yandex redirects back to the frontend callback with `code` + `state` ->
the frontend posts those to /yandex/verify -> backend trades the code for an
access token (using the app's OAuth secret, server-side), reads the profile,
creates/binds the account and mints the JWT session.

Why this shape (Yandex docs, yandex.ru/dev/id):
- Confidential app: the code is exchanged SERVER-SIDE with `client_secret`,
  so the access token never touches the browser. No PKCE (unlike VK) — the
  secret itself proves the exchange is ours.
- `state` is signed by us (HMAC + 10 min TTL) and echoed back unchanged, so a
  callback with a foreign/forged state is rejected before any token call.
- Registration and login are one flow: the account is created on the first
  successful exchange (matched by yandex_user_id thereafter).
- 152-FZ consent is captured on the site form (checkbox) and passed into
  /yandex/verify — stamped on new accounts, backfilled onto legacy ones.

State helpers mirror app.modules.vkauth.service (kept self-contained so each
provider module stands alone and stays independently testable).
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
from app.services.social_merge import merge_social_profile
from app.services.yandex_api import YandexApiError, get_yandex_api
from app.utils.tokens import create_access_token, create_refresh_token_payload

logger = get_logger(__name__)

# How long an authorize round-trip may take before the state is stale.
STATE_TTL_SECONDS = 600


def _state_key() -> bytes:
    """Server-side HMAC key for Yandex states (never leaves the backend)."""
    return settings.SECRET_KEY.encode()


def make_state() -> str:
    """Tamper-proof state binding a callback to an authorize start.

    Format `<ts>_<nonce>_<hmac32>` — carries its own issued-at so
    /yandex/verify can reject stale callbacks without a DB round-trip.
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


# Yandex consent screen (server-side constant — not a secret, entry URL).
YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"


def build_authorize_url(state: str) -> str:
    """Full Yandex consent URL: signed state + client_id + redirect_uri."""
    from urllib.parse import urlencode

    params = {
        "response_type": "code",
        "client_id": settings.YANDEX_CLIENT_ID,
        "redirect_uri": settings.YANDEX_REDIRECT_URI,
        "state": state,
    }
    scope = (settings.YANDEX_SCOPE or "").strip()
    if scope:
        params["scope"] = scope
    return f"{YANDEX_AUTHORIZE_URL}?{urlencode(params)}"


async def verify_yandex_code(
    code: str,
    state: str,
    db: AsyncSession,
    consent: bool = False,
) -> tuple[str, User, bool]:
    """Exchange the Yandex code, create/bind the account, mint the JWT.

    Returns (token, user, is_new). Raises 4xx on a bad state, a rejected
    exchange, or a profile read failure — never logs anyone in blind.
    """
    if not settings.yandex_enabled:
        raise HTTPException(
            status_code=503, detail="Вход через Яндекс не настроен")
    if not parse_state(state):
        raise HTTPException(
            status_code=400,
            detail="Неверная или просроченная сессия входа. Попробуйте снова.",
        )

    api = get_yandex_api()
    try:
        tokens = await api.exchange_code(code)
        profile = await api.user_info(tokens["access_token"])
    except YandexApiError as e:
        logger.warning("Yandex ID exchange failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail="Не удалось войти через Яндекс. Попробуйте позже.",
        )

    raw_id = profile.get("id")
    if raw_id is None:
        raise HTTPException(
            status_code=400, detail="Яндекс не вернул идентификатор пользователя")
    yandex_user_id = int(raw_id)

    first = (profile.get("first_name") or "").strip()
    last = (profile.get("last_name") or "").strip()
    email = _clean_email(profile.get("default_email"))
    # Yandex exposes the avatar as an id, not a URL — build the CDN link.
    avatar_id = (profile.get("default_avatar_id") or "").strip()
    avatar_url = (f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"
                  if avatar_id else None)

    from app.modules.auth.service import OFFER_VERSION, POLICY_VERSION

    result = await db.execute(
        select(User).where(User.yandex_user_id == yandex_user_id))
    user = result.scalar_one_or_none()
    is_new = False

    if user is None and email:
        # A pre-existing account with the same email: link it to Yandex instead
        # of creating a duplicate (same progressive-profiling rule as VK/MAX).
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is not None:
            user.yandex_user_id = yandex_user_id
            logger.info("Linked Yandex account to existing user_id=%s", user.id)

    if user is None:
        is_new = True
        logger.info("Creating new client via Yandex: yandex_user_id=%s",
                    yandex_user_id)
        user = User(
            name=compose_full_name(first, last) or "Яндекс Пользователь",
            last_name=last or None,
            email=email,
            phone=None,
            role=UserRole.CLIENT,
            hashed_password=None,  # Yandex-only auth (same as OTP/MAX/VK paths)
            # Yandex vouches the account + its verified default_email, so the
            # profile is trusted.
            is_verified=bool(email),
            yandex_user_id=yandex_user_id,
            avatar_url=avatar_url,
            # name came from Yandex: a later social login may refresh it, a
            # human edit ("user") will not be overwritten.
            name_source="yandex",
            # 152-FZ: consent checkbox on the Yandex login form.
            consent_at=(datetime.now(dt_timezone.utc) if consent else None),
            consent_policy_version=POLICY_VERSION if consent else None,
            consent_offer_version=OFFER_VERSION if consent else None,
        )
        db.add(user)
        await db.flush()
        from app.services.clients import get_or_create_profile
        await get_or_create_profile(db, user)
        logger.info("New client created via Yandex: user_id=%s", user.id)
    else:
        if user.is_active is False:
            raise HTTPException(status_code=403, detail="Аккаунт заблокирован.")
        # Smart merge: refresh name/avatar from Yandex, fill a missing email,
        # only ever raise is_verified — human-set fields are never lost.
        changed = await merge_social_profile(
            db, user, provider="yandex",
            first_name=first, last_name=last,
            email=email, avatar_url=avatar_url,
            verified=bool(email),
        )
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

    logger.info("User logged in via Yandex: user_id=%s is_new=%s",
                user.id, is_new)
    return access_token, user, is_new


def _clean_email(raw: Optional[str]) -> Optional[str]:
    """Lowercase/validate an email from the Yandex profile, or None."""
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

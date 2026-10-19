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
- The official instant-auth widget («мгновенная авторизация», sdk-suggest.js)
  skips the redirect: the widget hands an OAuth token to the browser and
  /yandex/verify hands it to verify_yandex_token, which validates it via
  user_info and reuses the exact same account tail as the code flow.
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
from app.models.user import User
from app.services.social_merge import (
    bind_social_login,
    complete_social_login,
    resolve_social_user,
)
from app.services.yandex_api import YandexApiError, get_yandex_api
from app.utils.phone import normalize_phone

logger = get_logger(__name__)

# How long an authorize round-trip may take before the state is stale.
STATE_TTL_SECONDS = 600


def _state_key() -> bytes:
    """Server-side HMAC key for Yandex states (never leaves the backend)."""
    return settings.SECRET_KEY.encode()


def make_state(link_user_id: Optional[int] = None) -> str:
    """Tamper-proof state binding a callback to an authorize start.

    Format `<ts>_<nonce>_<uid>_<hmac32>` — carries its own issued-at so
    /yandex/verify can reject stale callbacks without a DB round-trip. uid
    is the account asking to LINK this profile (0 = plain login); it sits
    inside the MAC, so a state can never be re-pointed at another user.
    """
    ts = str(int(datetime.now(dt_timezone.utc).timestamp()))
    # Hex nonce: never contains the "_" delimiter, so the state can always
    # be split back into exactly (ts, nonce, uid, mac) on parse.
    nonce = secrets.token_hex(8)
    uid = int(link_user_id or 0)
    mac = hmac.new(_state_key(), f"{ts}_{nonce}_{uid}".encode(), hashlib.sha256)
    return f"{ts}_{nonce}_{uid}_{mac.hexdigest()[:32]}"


def _parse_state(state: str) -> tuple[bool, Optional[int]]:
    """(valid, link_user_id) — format/MAC/TTL checked, uid inside the MAC."""
    try:
        ts_raw, nonce, uid_raw, mac = (state or "").split("_", 3)
        issued_at = int(ts_raw)
        link_user_id = int(uid_raw)
    except (ValueError, AttributeError):
        return False, None
    expect = hmac.new(
        _state_key(), f"{ts_raw}_{nonce}_{uid_raw}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    if not hmac.compare_digest(expect, mac):
        return False, None
    age = datetime.now(dt_timezone.utc).timestamp() - issued_at
    if not (0 <= age <= STATE_TTL_SECONDS):
        return False, None
    return True, (link_user_id or None)


def parse_state(state: str) -> bool:
    """True when the state was minted by us and is still fresh."""
    ok, _ = _parse_state(state)
    return ok


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
    state_ok, link_user_id = _parse_state(state)
    if not state_ok:
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
    return await _login_with_profile(db, profile, consent, link_user_id)


async def verify_yandex_token(
    access_token: str,
    db: AsyncSession,
    consent: bool = False,
) -> tuple[str, User, bool]:
    """Widget flow: the official sdk-suggest widget delivered a token.

    Unlike the code flow there is no redirect and no signed state — a valid
    OAuth token IS the proof of authentication, but only for the app it was
    issued to: we first check oauth.yandex.ru/info that the token belongs to
    OUR client_id (fail closed), then read the profile (revoked tokens fail
    there) and reuse the same create/bind path as the code flow.
    """
    if not settings.yandex_enabled:
        raise HTTPException(
            status_code=503, detail="Вход через Яндекс не настроен")
    api = get_yandex_api()
    try:
        token_client = await api.token_client_id(access_token)
    except YandexApiError as e:
        logger.warning("Yandex ID token info call failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Не удалось подтвердить вход через Яндекс. "
                   "Попробуйте снова.",
        )
    if not token_client or token_client != settings.YANDEX_CLIENT_ID:
        logger.warning(
            "Yandex widget token issued to client_id=%r (expected %r)",
            token_client, settings.YANDEX_CLIENT_ID)
        raise HTTPException(
            status_code=401,
            detail="Токен выдан другому приложению. "
                   "Войдите через Яндекс заново.",
        )
    try:
        profile = await api.user_info(access_token)
    except YandexApiError as e:
        logger.warning("Yandex ID token check failed: %s", e)
        raise HTTPException(
            status_code=401,
            detail="Не удалось подтвердить вход через Яндекс. "
                   "Попробуйте снова.",
        )
    return await _login_with_profile(db, profile, consent)


async def _login_with_profile(
    db: AsyncSession, profile: dict, consent: bool,
    link_user_id: Optional[int] = None,
) -> tuple[str, User, bool]:
    """Shared tail of both verify flows: profile -> account -> JWT session.

    link_user_id (from a signed start state) switches the tail into the
    «Привязать Яндекс» mode: the profile binds to that account instead of
    being used to find or create one.
    """
    raw_id = profile.get("id")
    if raw_id is None:
        raise HTTPException(
            status_code=400, detail="Яндекс не вернул идентификатор пользователя")
    yandex_user_id = int(raw_id)

    first = (profile.get("first_name") or "").strip()
    last = (profile.get("last_name") or "").strip()
    email = _clean_email(profile.get("default_email"))
    # default_phone appears once the app carries the login:phone scope; the
    # number is confirmed by Yandex to belong to this very account.
    phone = _clean_phone((profile.get("default_phone") or {}).get("number"))
    # Yandex exposes the avatar as an id, not a URL — build the CDN link.
    avatar_id = (profile.get("default_avatar_id") or "").strip()
    avatar_url = (f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"
                  if avatar_id else None)

    # One shared resolution for every social login («Единый вход»): yandex-id
    # → confirmed phone → confirmed email → create; contacts land on the
    # account through the contact service (verified_via="social").
    if link_user_id is not None:
        # «Привязать Яндекс»: the signed state names the current account —
        # the profile is linked to it, never re-resolved by fields.
        user = await bind_social_login(
            db,
            user_id=link_user_id,
            provider="yandex",
            social_id=yandex_user_id,
            social_field="yandex_user_id",
            first_name=first,
            last_name=last,
            phone=phone,
            phone_confirmed=bool(phone),
            email=email,
            email_confirmed=bool(email),
            avatar_url=avatar_url,
        )
        is_new = False
    else:
        user, is_new = await resolve_social_user(
            db,
            provider="yandex",
            social_id=yandex_user_id,
            social_field="yandex_user_id",
            first_name=first,
            last_name=last,
            phone=phone,
            phone_confirmed=bool(phone),
            email=email,
            email_confirmed=bool(email),
            avatar_url=avatar_url,
            fallback_name="Яндекс Пользователь",
            consent=consent,
        )
    access_token = await complete_social_login(db, user)
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


def _clean_phone(raw: Optional[str]) -> Optional[str]:
    """Normalize a phone from the Yandex profile; None when unparseable."""
    if not raw:
        return None
    try:
        return normalize_phone(str(raw))
    except ValueError:
        return None


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

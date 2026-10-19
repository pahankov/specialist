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
from app.models.user import User
from app.services.social_merge import (
    bind_social_login,
    complete_social_login,
    resolve_social_user,
)
from app.services.vk_api import VkApiError, get_vk_api

logger = get_logger(__name__)

# How long an authorize round-trip may take before the state is stale.
STATE_TTL_SECONDS = 600


def _state_key() -> bytes:
    """Server-side HMAC key for VK states (never leaves the backend)."""
    return settings.SECRET_KEY.encode()


def make_state(link_user_id: Optional[int] = None) -> str:
    """Tamper-proof state binding a callback to an authorize start.

    Format `<ts>_<nonce>_<uid>_<hmac32>` — carries its own issued-at so
    /vk/verify can reject stale callbacks without a DB round-trip. uid is
    the account asking to LINK this profile (0 = plain login); it sits
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

    For new accounts without consent (1.80.0), returns a challenge token
    instead of JWT — the frontend shows ConsentScreen, then calls
    /auth/consent/complete.
    """
    if not settings.vk_enabled:
        raise HTTPException(status_code=503, detail="Вход через VK не настроен")
    state_ok, link_user_id = _parse_state(state)
    if not state_ok:
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
    # VK ID returns a ready-made avatar URL on the profile block.
    avatar_url = (vk_user.get("avatar") or "").strip() or None

    # One shared resolution for every social login («Единый вход»): vk-id →
    # confirmed phone → confirmed email → create; contacts land on the
    # account through the contact service. VK's grey "verified" tick no
    # longer feeds users.is_verified — verification lives on contacts now.
    # The phone scope is not requested yet, hence no phone here.
    if link_user_id is not None:
        # «Привязать VK»: the signed state names the current account — the
        # profile is linked to it, never re-resolved by fields.
        user = await bind_social_login(
            db,
            user_id=link_user_id,
            provider="vk",
            social_id=vk_user_id,
            social_field="vk_user_id",
            first_name=first,
            last_name=last,
            email=email,
            email_confirmed=bool(email),  # an email from VK is provider-vouched
            avatar_url=avatar_url,
        )
        is_new = False
    else:
        user, is_new = await resolve_social_user(
            db,
            provider="vk",
            social_id=vk_user_id,
            social_field="vk_user_id",
            first_name=first,
            last_name=last,
            email=email,
            email_confirmed=bool(email),  # an email from VK is provider-vouched
            avatar_url=avatar_url,
            fallback_name="VK Пользователь",
            consent=consent,
            defer_creation=(link_user_id is None and not consent),
        )
    # No consent and none stamped yet (new OR abandoned pending account):
    # return a challenge instead of a session — the frontend shows the
    # ConsentScreen, then /auth/consent/complete stamps consent + logs in.
    if not link_user_id and not consent and user.consent_at is None:
        from app.modules.auth.service import _create_challenge_token
        row = (await db.execute(
            select(User).where(User.id == user.id)
        )).scalar_one_or_none()
        challenge = _create_challenge_token(
            user.id, (row.phone if row else "") or "")
        return challenge, user, is_new
    access_token = await complete_social_login(db, user)
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

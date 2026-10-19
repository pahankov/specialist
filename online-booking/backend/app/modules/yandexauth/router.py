"""Yandex ID auth endpoints (OAuth 2.0 Authorization Code Flow)."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies.auth import get_current_user_optional
from app.logging_config import get_logger
from app.middleware.rate_limit import limiter
from app.models.user import User
from app.modules.yandexauth import schemas
from app.modules.yandexauth import service
from app.services.audit import log_action
from app.utils.cookies_http import set_auth_cookies

logger = get_logger(__name__)

router = APIRouter()


@router.post("/yandex/start", response_model=schemas.YandexStartResponse)
@limiter.limit("10/minute")
async def yandex_start(
    request: Request,
    req: schemas.YandexStartRequest,
    user: Optional[User] = Depends(get_current_user_optional),
):
    """Mint a signed state + the Yandex authorize URL for the redirect.

    Yandex has no PKCE, so the start call only produces the HMAC state and
    the consent URL — the app secret never leaves the backend. With
    link=True the signed state names the current account («Привязать
    Яндекс»), so the callback binds the profile there.
    """
    if not settings.yandex_enabled:
        raise HTTPException(
            status_code=503, detail="Вход через Яндекс не настроен")
    if req.link:
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Войдите в аккаунт, чтобы привязать профиль",
            )
        state = service.make_state(link_user_id=user.id)
    else:
        state = service.make_state()
    return {
        "authorize_url": service.build_authorize_url(state),
        "state": state,
        "client_id": settings.YANDEX_CLIENT_ID,
        "redirect_uri": settings.YANDEX_REDIRECT_URI,
        "suggest_redirect_uri": settings.YANDEX_SUGGEST_REDIRECT_URI,
    }


@router.post("/yandex/verify", response_model=schemas.YandexVerifyResponse)
@limiter.limit("10/minute")
async def yandex_verify(
    request: Request,
    response: Response,
    req: schemas.YandexVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trade the callback code OR the widget token for a session (sets cookies).

    Redirect flow: the backend holds the Yandex OAuth secret, so the code is
    exchanged here — the access token never reaches the browser. Widget flow
    («мгновенная авторизация»): the SDK already delivered a token to the
    browser; it is validated server-side via user_info before login.
    """
    if not settings.yandex_enabled:
        raise HTTPException(
            status_code=503, detail="Вход через Яндекс не настроен")
    if isinstance(req, schemas.YandexVerifyTokenRequest):
        access_token, user, is_new = await service.verify_yandex_token(
            req.access_token, db, consent=req.consent,
        )
    else:
        access_token, user, is_new = await service.verify_yandex_code(
            req.code, req.state, db, consent=req.consent,
        )
    # A challenge (new/pending account without consent) is not a session:
    # don't set cookies — the frontend shows ConsentScreen, then calls
    # /auth/consent/complete.
    from app.modules.auth.service import is_challenge_token

    if is_challenge_token(access_token):
        return {
            "access_token": access_token,  # actually a challenge token
            "token_type": "bearer",
            "is_new_user": is_new,
            "challenge": access_token,
        }
    cookie_token = await service.get_latest_refresh_token_value(db, user.id)
    set_auth_cookies(response, access_token, cookie_token)
    await log_action(
        db, user.id, "login", "yandex_auth", user.id,
        f"Вход через Яндекс: {user.email or user.phone}", level="info",
    )
    await db.commit()
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": is_new,
    }

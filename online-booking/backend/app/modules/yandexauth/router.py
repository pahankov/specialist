"""Yandex ID auth endpoints (OAuth 2.0 Authorization Code Flow)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logging_config import get_logger
from app.middleware.rate_limit import limiter
from app.modules.yandexauth import schemas
from app.modules.yandexauth import service
from app.services.audit import log_action
from app.utils.cookies_http import set_auth_cookies

logger = get_logger(__name__)

router = APIRouter()


@router.post("/yandex/start", response_model=schemas.YandexStartResponse)
@limiter.limit("10/minute")
async def yandex_start(request: Request, req: schemas.YandexStartRequest):
    """Mint a signed state + the Yandex authorize URL for the redirect.

    Yandex has no PKCE, so the start call only produces the HMAC state and
    the consent URL — the app secret never leaves the backend.
    """
    if not settings.yandex_enabled:
        raise HTTPException(
            status_code=503, detail="Вход через Яндекс не настроен")
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
    if req.access_token is not None:
        access_token, user, is_new = await service.verify_yandex_token(
            req.access_token, db, consent=req.consent,
        )
    else:
        access_token, user, is_new = await service.verify_yandex_code(
            req.code or "", req.state or "", db, consent=req.consent,
        )
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

"""VK ID auth endpoints (OAuth 2.0 Authorization Code Flow + PKCE)."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logging_config import get_logger
from app.middleware.rate_limit import limiter
from app.modules.vkauth import schemas
from app.modules.vkauth import service
from app.services.audit import log_action
from app.utils.cookies_http import set_auth_cookies

logger = get_logger(__name__)

router = APIRouter()


@router.post("/vk/start", response_model=schemas.VkStartResponse)
@limiter.limit("10/minute")
async def vk_start(request: Request, req: schemas.VkStartRequest):
    """Mint a signed state + the VK authorize URL for the browser redirect.

    The PKCE code_challenge is generated in the browser and only its digest
    travels here, so the code_verifier never leaves the client until the
    final /vk/verify exchange.
    """
    if not settings.vk_enabled:
        raise HTTPException(status_code=503, detail="Вход через VK не настроен")
    state = service.make_state()
    return {
        "authorize_url": service.build_authorize_url(state, req.code_challenge),
        "state": state,
        "client_id": settings.VK_CLIENT_ID,
        "redirect_uri": settings.VK_REDIRECT_URI,
    }


@router.post("/vk/verify", response_model=schemas.VkVerifyResponse)
@limiter.limit("10/minute")
async def vk_verify(
    request: Request,
    response: Response,
    req: schemas.VkVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trade the callback code for a session (sets cookies).

    The backend holds the VK service token, so the code is exchanged here —
    access/refresh/id tokens never reach the browser.
    """
    if not settings.vk_enabled:
        raise HTTPException(status_code=503, detail="Вход через VK не настроен")
    access_token, user, is_new = await service.verify_vk_code(
        req.code, req.device_id, req.state, req.code_verifier, db,
        consent=req.consent,
    )
    cookie_token = await service.get_latest_refresh_token_value(db, user.id)
    set_auth_cookies(response, access_token, cookie_token)
    await log_action(
        db, user.id, "login", "vk_auth", user.id,
        f"Вход через VK: {user.email or user.phone}", level="info",
    )
    await db.commit()
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": is_new,
    }

"""MAX chat-bot auth endpoints + webhook receiver."""
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.logging_config import get_logger
from app.middleware.rate_limit import limiter
from app.modules.maxauth import schemas
from app.modules.maxauth import service
from app.services.audit import log_action
from app.services.max_api import MaxApiError, get_max_api
from app.utils.cookies_http import set_auth_cookies

logger = get_logger(__name__)

router = APIRouter()
webhook_router = APIRouter()


def _bot_card() -> dict:
    return {
        "bot_username": settings.MAX_BOT_USERNAME,
        "bot_url": settings.MAX_BOT_URL
        or (f"https://max.ru/{settings.MAX_BOT_USERNAME}"
            if settings.MAX_BOT_USERNAME else ""),
    }


# ─── Site side ─────────────────────────────────────────────────────

@router.post("/max/start", response_model=schemas.MaxStartResponse)
@limiter.limit("10/minute")
async def max_start(
    request: Request,
    req: schemas.MaxStartRequest,
    db: AsyncSession = Depends(get_db),
):
    """Issue a 6-digit code shown on site; user retypes it to the MAX bot."""
    if not settings.max_enabled:
        raise HTTPException(status_code=503, detail="Вход через MAX не настроен")
    code, ttl = await service.start_max_auth(req.phone, db)
    return {
        "code": code,
        "expires_in": ttl,
        **_bot_card(),
    }


@router.post("/max/status", response_model=schemas.MaxStatusResponse)
@limiter.limit("10/minute")
async def max_status(
    request: Request,
    response: Response,
    req: schemas.MaxStatusRequest,
    db: AsyncSession = Depends(get_db),
):
    """Poll bot confirmation. Issues the JWT session once (sets cookies)."""
    if not settings.max_enabled:
        return {"status": "disabled", "token_type": "bearer"}
    state = await service.get_max_status(req.phone, db)
    if state != "verified":
        return {"status": state, "token_type": "bearer"}
    access_token, user, is_new = await service.complete_max_session(req.phone, db)
    cookie_token = await service.get_latest_refresh_token_value(db, user.id)
    set_auth_cookies(response, access_token, cookie_token)
    await log_action(
        db, user.id, "login", "max_auth", user.id,
        f"Вход через MAX: {user.phone}", level="info",
    )
    await db.commit()
    return {
        "status": "verified",
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": is_new,
    }


# ─── MAX side (webhook) ────────────────────────────────────────────

@webhook_router.post("/webhook")
async def max_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive MAX Bot API updates (message_created/bot_started).

    Secret check first (X-Max-Bot-Api-Secret); always 200 on processed
    updates so MAX stops retrying (retries x10 with backoff otherwise).
    """
    if settings.MAX_WEBHOOK_SECRET:
        got = request.headers.get("X-Max-Bot-Api-Secret", "")
        if got != settings.MAX_WEBHOOK_SECRET:
            logger.warning("MAX webhook: secret mismatch")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Bad webhook secret"
            )
    try:
        update = await request.json()
    except Exception:
        logger.warning("MAX webhook: invalid JSON body")
        return {"ok": False}

    update_type = (update or {}).get("update_type")
    logger.info("MAX webhook: update_type=%s", update_type)

    if update_type == "bot_started":
        await _reply_to_sender(update, (
            "Здравствуйте! Это бот электронной записи.\n"
            "Чтобы войти на сайт, введите номер телефона там, "
            "получите 6-значный код и отправьте его сюда."
        ))
        return {"ok": True}

    if update_type == "message_created":
        code, sender = service.parse_update_code(update)
        sender_id = (sender or {}).get("user_id")
        if code is None or sender_id is None:
            await _reply_to_sender(
                update, "Пришлите 6-значный код с сайта для входа.")
            return {"ok": True}
        name = service.sender_display_name(sender or {})
        outcome = await service.confirm_max_code(db, sender_id, name, code)
        await _reply_to_sender(update, _outcome_text(outcome))
        return {"ok": True, "outcome": outcome}

    return {"ok": True}


def _outcome_text(outcome: str) -> str:
    return {
        "confirmed": "Код принят! Вернитесь на сайт — вы уже вошли.",
        "unknown": "Такой код не найден. Проверьте цифры и запросите новый на сайте.",
        "expired": "Код истёк. Запросите новый код на сайте.",
        "already": "Этот код уже использован. Запросите новый на сайте.",
    }.get(outcome, "Пришлите 6-значный код с сайта для входа.")


async def _reply_to_sender(update: dict, text: str) -> None:
    """Best-effort bot reply; never fails the webhook (else MAX retries)."""
    try:
        message = (update or {}).get("message") or {}
        sender = message.get("sender") or {}
        # Dialog reply target: message sender, else the dialog chat itself
        # (bot_started carries user/chat_id but no message.sender).
        target = sender.get("user_id") or (update or {}).get("chat_id")
        if not target:
            return
        await get_max_api().send_message(int(target), text)
    except (MaxApiError, ValueError, TypeError) as e:
        logger.warning("MAX reply failed (best-effort): %s", e)

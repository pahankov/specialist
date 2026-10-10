"""MAX chat-bot auth endpoints + webhook receiver (SMS-style flow)."""
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
    """Register a pending MAX request; push the code if the dialog is known."""
    if not settings.max_enabled:
        raise HTTPException(status_code=503, detail="Вход через MAX не настроен")
    ttl = await service.start_max_auth(req.phone, db)
    delivered = False
    prepared = await service.prepare_push_code(req.phone, db)
    if prepared is not None:
        target, code = prepared
        try:
            text, attachments = service.build_code_message(code)
            await get_max_api().send_message(target, text, attachments)
            delivered = True
            logger.info("MAX code pushed to known dialog for %s", req.phone)
        except MaxApiError as e:
            # Push failed (blocked bot, network) — share-number flow still works.
            logger.warning("MAX push failed, fallback to share flow: %s", e)
    return {"delivered": delivered, "expires_in": ttl, **_bot_card()}


@router.post("/max/verify", response_model=schemas.MaxVerifyResponse)
@limiter.limit("10/minute")
async def max_verify(
    request: Request,
    response: Response,
    req: schemas.MaxVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    """Check the dialog-delivered code, mint the JWT session (sets cookies)."""
    if not settings.max_enabled:
        raise HTTPException(status_code=503, detail="Вход через MAX не настроен")
    access_token, user, is_new = await service.verify_max_code(
        req.phone, req.code, db
    )
    cookie_token = await service.get_latest_refresh_token_value(db, user.id)
    set_auth_cookies(response, access_token, cookie_token)
    await log_action(
        db, user.id, "login", "max_auth", user.id,
        f"Вход через MAX: {user.phone}", level="info",
    )
    await db.commit()
    return {
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
        await _reply_with_keyboard(
            update,
            "Здравствуйте! Это бот электронной записи.\n"
            "Введите номер на сайте и нажмите «Получить код в MAX», "
            "а затем поделитесь номером здесь — пришлём код для входа.",
        )
        return {"ok": True}

    if update_type == "message_created":
        message = (update or {}).get("message") or {}
        sender = message.get("sender") or {}
        sender_id = sender.get("user_id")
        if sender_id is None:
            return {"ok": True}

        # 1. Contact share (HMAC-verified number when it matches).
        phone, verified, name = service.parse_contact_phone(message)
        # 2. Fallback: typed phone text.
        if phone is None:
            body = message.get("body") or {}
            text = body.get("text") or message.get("text") or ""
            phone = service.parse_phone_text(text)
            name = service.sender_display_name(sender)
        if phone is None:
            await _reply_to_sender(
                update,
                "Пришлите номер телефона (или нажмите «Поделиться номером»), "
                "а код для входа придёт сюда же.",
            )
            return {"ok": True}

        code = await service.deliver_code_to_dialog(
            db, phone, int(sender_id), name, verified)
        if code is None:
            await _reply_to_sender(
                update,
                "Заявки с таким номером нет. Сначала введите номер на сайте "
                "и нажмите «Получить код в MAX».",
            )
            return {"ok": True, "outcome": "no_pending"}
        await _reply_code(update, code)
        return {"ok": True, "outcome": "delivered"}

    return {"ok": True}


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


async def _reply_with_keyboard(update: dict, text: str) -> None:
    """bot_started reply with a request_contact button."""
    try:
        message = (update or {}).get("message") or {}
        sender = message.get("sender") or {}
        target = sender.get("user_id") or (update or {}).get("chat_id")
        if not target:
            return
        await get_max_api().send_message(
            int(target), text,
            attachments=[{
                "type": "inline_keyboard",
                "payload": {"buttons": [[
                    {"type": "request_contact", "text": "Поделиться номером"},
                ]]},
            }],
        )
    except (MaxApiError, ValueError, TypeError) as e:
        logger.warning("MAX keyboard reply failed (best-effort): %s", e)


async def _reply_code(update: dict, code: str) -> None:
    """Deliver the login code into the dialog (+ copy-to-clipboard button)."""
    try:
        message = (update or {}).get("message") or {}
        sender = message.get("sender") or {}
        target = sender.get("user_id") or (update or {}).get("chat_id")
        if not target:
            return
        text, attachments = service.build_code_message(code)
        await get_max_api().send_message(int(target), text, attachments)
    except (MaxApiError, ValueError, TypeError) as e:
        logger.warning("MAX code reply failed (best-effort): %s", e)

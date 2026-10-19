"""MAX chat-bot auth endpoints + webhook receiver (SMS-style flow)."""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
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

# Retry delay when MAX reports dialog.not.found right after bot_started
# (dialog creation races the event delivery).
DIALOG_RETRY_DELAY = 4

# Reply to the «Начать заново» callback: re-issue the one-time
# request_contact keyboard so the dialog can run the flow again.
RESTART_TEXT = ("Хорошо! Нажмите «Поделиться номером» ниже — "
                "пришлю новый код для входа.")


def _bot_card() -> dict:
    return {
        "bot_username": settings.MAX_BOT_USERNAME,
        "bot_url": settings.MAX_BOT_URL
        or (f"https://max.ru/{settings.MAX_BOT_USERNAME}"
            if settings.MAX_BOT_USERNAME else ""),
        "bot_name": settings.MAX_BOT_NAME or settings.MAX_BOT_USERNAME,
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
    otp_id, ttl = await service.start_max_auth(req.phone, db)
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
    return {
        "delivered": delivered,
        "deeplink": service.make_start_deeplink(otp_id),
        "expires_in": ttl,
        **_bot_card(),
    }


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
        req.phone, req.code, db, consent=req.consent
    )
    # If a challenge is returned (new account without consent), don't set
    # cookies — the frontend shows ConsentScreen, then calls /auth/consent/complete.
    if req.consent is False and is_new and "challenge" in access_token:
        return {
            "access_token": access_token,  # actually a challenge token
            "token_type": "bearer",
            "is_new_user": is_new,
            "challenge": access_token,
        }
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
async def max_webhook(
    request: Request,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Receive MAX Bot API updates (message_created/bot_started/message_callback).

    Secret check first (X-Max-Bot-Api-Secret); always 200 on processed
    updates so MAX stops retrying (retries x10 with backoff otherwise).
    Dialog replies go out as BackgroundTasks so MAX gets its 2xx right
    after the DB write: a slow send (dialog.not.found retry) or a failed
    one can never look like a failed delivery — and enough failed
    deliveries is exactly how the bot gets auto-unsubscribed after 8h.
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
        # Deeplink open (?start=<otp_id>_<hmac>) or a plain "start" tap.
        # SECURITY: opening a link proves nothing about the phone — the code
        # is delivered only after an HMAC-verified contact share below.
        # Here the bot always answers with the share-number keyboard.
        payload = (update or {}).get("payload") or ""
        sender = ((update or {}).get("message") or {}).get("sender") or {}
        if not sender:
            sender = (update or {}).get("user") or {}
        sender_id = sender.get("user_id")
        otp_id = service.parse_start_payload(payload) if payload else None
        pending = False
        if otp_id is not None and sender_id is not None:
            pending = (await service.get_pending_otp(otp_id, db)) is not None
        text = (
            "Вы начали вход на сайте. Подтвердите номер кнопкой "
            "«Поделиться номером» ниже — пришлём код для входа."
            if pending else
            "Здравствуйте! Это бот электронной записи.\n"
            "Поделитесь номером телефона кнопкой ниже — пришлём код "
            "для входа."
        )
        background.add_task(_reply_with_keyboard, update, text)
        return ({"ok": True, "outcome": "share_required"} if pending
                else {"ok": True})

    if update_type == "message_callback":
        # Inline button tap. The only callback button we send is «Начать
        # заново» (under the code message): MAX consumes the request_contact
        # keyboard after its first use, so this button is the one in-chat way
        # to bring it back. The /answers ack is best-effort — it only stops
        # the tapped button's spinner; failures must not drop the reply.
        callback = (update or {}).get("callback") or {}
        sender = callback.get("sender") or {}
        sender_id = sender.get("user_id")
        if sender_id is None:
            return {"ok": True}
        logger.info(
            "MAX webhook: callback payload=%s (share keyboard re-issued)",
            callback.get("payload"),
        )
        callback_id = callback.get("callback_id")
        if callback_id:
            background.add_task(_answer_callback, str(callback_id))
        background.add_task(_reply_with_keyboard, update, RESTART_TEXT)
        return {"ok": True, "outcome": "share_required"}

    if update_type == "message_created":
        message = (update or {}).get("message") or {}
        sender = message.get("sender") or {}
        sender_id = sender.get("user_id")
        if sender_id is None:
            return {"ok": True}

        # 1. Contact share: platform-proven only when the HMAC matches.
        phone, verified, name, vcf_email = service.parse_contact_phone(message)
        username = service.sender_username(sender)
        if not verified:
            # 2. Anything typed is self-asserted — anyone can type anyone's
            # number — so it NEVER unlocks a code. Point at the button.
            body = message.get("body") or {}
            text = body.get("text") or message.get("text") or ""
            if phone is not None:
                # Contact attachment present, HMAC mismatch: the number
                # could not be platform-verified (forgery/config drift).
                hint = ("Не получилось подтвердить номер. Нажмите "
                        "«Поделиться номером» ещё раз.")
            elif service.parse_phone_text(text) is not None:
                hint = ("Код придёт только после подтверждения номера. "
                        "Нажмите «Поделиться номером» ниже — пришлём код "
                        "для входа.")
            else:
                # Not a phone — repeat the button: the first keyboard
                # appeared only at bot_started and is easy to miss.
                hint = ("Пришлите номер телефона кнопкой «Поделиться "
                        "номером» ниже — код для входа придёт сюда же.")
            background.add_task(_reply_with_keyboard, update, hint)
            return {"ok": True, "outcome": "share_required"}

        # Platform proved this number belongs to the sender: deliver the
        # code (a pending site request gets a fresh code; a verified share
        # without one opens the request itself).
        code = await service.deliver_code_to_dialog(
            db, phone, int(sender_id), name, True,
            username=username, email=vcf_email)
        if code is None:
            # Nothing delivered (should not happen for a verified share) —
            # fall back to the share flow instead of a broken reply.
            background.add_task(
                _reply_with_keyboard, update,
                "Не получилось выдать код. Нажмите «Поделиться номером» "
                "ещё раз.",
            )
            return {"ok": True, "outcome": "share_required"}
        background.add_task(_reply_code, update, code)
        return {"ok": True, "outcome": "delivered"}

    return {"ok": True}


def _resolve_target(update: dict):
    """Dialog reply target: message sender, then update user, then callback
    sender, then chat.

    bot_started carries `user` but no message.sender; message_callback keeps
    the tap author in `callback.sender`; chat_id is the last resort (a
    stale/wrong chat id yields dialog.not.found — retried below).
    """
    update = update or {}
    message = update.get("message") or {}
    sender = message.get("sender") or {}
    user = update.get("user") or {}
    callback = update.get("callback") or {}
    callback_sender = callback.get("sender") or {}
    return (
        sender.get("user_id")
        or user.get("user_id")
        or callback_sender.get("user_id")
        or update.get("chat_id")
    )


async def _send_with_dialog_retry(target: int, text: str, attachments=None) -> None:
    """Send once; on dialog.not.found retry once after a short delay."""
    import asyncio

    try:
        await get_max_api().send_message(target, text, attachments)
        return
    except MaxApiError as e:
        if "dialog.not.found" not in str(e):
            raise
        logger.info(
            "MAX dialog not ready for %s, retrying once in %ss",
            target, DIALOG_RETRY_DELAY,
        )
        await asyncio.sleep(DIALOG_RETRY_DELAY)
        await get_max_api().send_message(target, text, attachments)


async def _answer_callback(callback_id: str) -> None:
    """Best-effort /answers ack so the tapped button stops its spinner."""
    try:
        await get_max_api().answer_callback(
            callback_id, "Отправляю кнопку ещё раз…")
    except (MaxApiError, ValueError, TypeError) as e:
        logger.warning("MAX callback ack failed (best-effort): %s", e)


async def _reply_with_keyboard(update: dict, text: str) -> None:
    """bot_started reply with a request_contact button."""
    try:
        target = _resolve_target(update)
        if not target:
            return
        await _send_with_dialog_retry(
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
        target = _resolve_target(update)
        if not target:
            return
        text, attachments = service.build_code_message(code)
        await _send_with_dialog_retry(int(target), text, attachments)
    except (MaxApiError, ValueError, TypeError) as e:
        logger.warning("MAX code reply failed (best-effort): %s", e)

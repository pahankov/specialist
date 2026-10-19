"""Outgoing email (1.79.0): SMTP from the site mailbox, brand voice.

Sending requires SMTP_USER + SMTP_PASSWORD (a Yandex APP PASSWORD) in the
server .env; without them the module is a safe no-op that only logs — local
dev and pre-deploy runs never send mail and never crash.

Every message gets the agreed signature, the sender is «Электронная запись»
<SMTP_USER> (overridable via SMTP_FROM_NAME / SMTP_FROM_EMAIL). Blocking
smtplib runs in a worker thread; failures are logged and returned as False
(callers show a generic «не удалось отправить» error), never raised — a dead
mailbox must not break booking or login flows.

Plain smtplib in a thread (not aiosmtplib): no new dependency, a few letters
a day, trivially testable.
"""
import asyncio
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

# TTL of email codes (password reset / email confirmation) — flows reuse it.
EMAIL_CODE_TTL_MINUTES = 15

SIGNATURE = (
    "—\n"
    "Электронная запись · beauty-specialist.ru\n"
    "Письмо отправлено автоматически, отвечать на него не нужно."
)


def with_signature(text: str) -> str:
    """Agreed brand sign-off appended to every outgoing letter."""
    return f"{text.rstrip()}\n\n{SIGNATURE}\n"


def _send_sync(to: str, subject: str, text: str) -> None:
    msg = EmailMessage()
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.smtp_from_email))
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(with_signature(text))

    ctx = ssl.create_default_context()
    if settings.SMTP_PORT == 465:
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT,
                              timeout=20, context=ctx) as s:
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT,
                          timeout=20) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.ehlo()
            s.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            s.send_message(msg)


async def send_email(to: str, subject: str, text: str) -> bool:
    """Send one letter. True = handed to the SMTP server.

    Not configured -> logs the letter and returns False (dev no-op).
    SMTP errors are logged and swallowed -> False.
    """
    to = (to or "").strip()
    if not to:
        logger.warning("Email skipped: empty recipient (subject=%r)", subject)
        return False
    if not settings.smtp_enabled:
        logger.info("SMTP disabled — letter not sent: to=%s subject=%r",
                    to, subject)
        return False
    try:
        await asyncio.to_thread(_send_sync, to, subject, text)
    except Exception as exc:  # noqa: BLE001 — письмо не должно ронять флоу
        logger.error("SMTP send failed: to=%s subject=%r error=%s",
                     to, subject, exc)
        return False
    logger.info("Email sent: to=%s subject=%r", to, subject)
    return True


# ─── Semantic builders (single place for the wording) ────────────────

async def send_password_reset_code(to: str, code: str) -> bool:
    subject = "Сброс пароля · Электронная запись"
    text = (
        "Здравствуйте!\n\n"
        "Вы запросили сброс пароля в системе онлайн-записи "
        "beauty-specialist.ru.\n"
        f"Код подтверждения: {code}\n"
        f"Код действует {EMAIL_CODE_TTL_MINUTES} минут.\n\n"
        "Если вы не запрашивали сброс пароля — просто проигнорируйте "
        "это письмо, пароль останется прежним."
    )
    return await send_email(to, subject, text)


async def send_email_confirm_code(to: str, code: str) -> bool:
    subject = "Подтверждение почты · Электронная запись"
    text = (
        "Здравствуйте!\n\n"
        f"Код для подтверждения адреса {to}: {code}\n"
        f"Код действует {EMAIL_CODE_TTL_MINUTES} минут.\n\n"
        "Введите его в личном кабинете на beauty-specialist.ru. "
        "Если вы не добавляли этот адрес — проигнорируйте письмо."
    )
    return await send_email(to, subject, text)

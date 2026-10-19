"""Email codes service — issue / verify six-digit codes sent by letter.

Backs the password reset (and, later, email confirmation). Design notes
(LOCAL.md «Единый вход»):

- codes are random six digits, stored as sha256 (hash_otp_code), single-use;
- TTL comes from the mailer (EMAIL_CODE_TTL_MINUTES);
- five wrong entries burn the code (attempts) — no brute force;
- issuing a new code invalidates the previous unused ones for the same
  email + purpose, so only the freshest letter works;
- every state change is committed inside this module: a failed attempt
  must survive the HTTP error that follows it.

Callers get :class:`EmailCodeError` carrying an HTTP hint; the module
stays free of FastAPI so it can be unit-tested and reused.
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.email_code import EmailCode
from app.services.contacts import normalize_email
from app.services.mailer import EMAIL_CODE_TTL_MINUTES
from app.utils.security import hash_otp_code

logger = get_logger(__name__)

PURPOSE_RESET_PASSWORD = "reset_password"
PURPOSE_CONFIRM_EMAIL = "confirm_email"
PURPOSES = (PURPOSE_RESET_PASSWORD, PURPOSE_CONFIRM_EMAIL)

MAX_ATTEMPTS = 5


class EmailCodeError(Exception):
    """Code can not be verified. Carries the HTTP status for the caller."""

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _utc(stamp: datetime) -> datetime:
    """SQLite hands back naive datetimes — they are UTC by convention."""
    if stamp.tzinfo is None:
        return stamp.replace(tzinfo=timezone.utc)
    return stamp


async def issue_code(db: AsyncSession, email: str, purpose: str) -> str:
    """Create a fresh single-use code for the address; returns the plain code.

    Previous unused codes for the same email + purpose are burned first:
    only the latest letter must work.
    """
    if purpose not in PURPOSES:
        raise ValueError(f"Unsupported purpose: {purpose!r}")
    email = normalize_email(email)

    previous = (await db.execute(
        select(EmailCode).where(
            EmailCode.email == email,
            EmailCode.purpose == purpose,
            EmailCode.is_used == False,  # noqa: E712
        )
    )).scalars().all()
    for row in previous:
        row.is_used = True

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(EmailCode(
        email=email,
        purpose=purpose,
        code_hash=hash_otp_code(code),
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=EMAIL_CODE_TTL_MINUTES),
        is_used=False,
        attempts=0,
    ))
    await db.commit()
    logger.info("Email code issued: email=%s purpose=%s burned_previous=%s",
                email, purpose, len(previous))
    return code


async def verify_code(
    db: AsyncSession, email: str, purpose: str, code: str
) -> None:
    """Check and burn a code. Raises EmailCodeError on any problem."""
    email = normalize_email(email)
    row = (await db.execute(
        select(EmailCode)
        .where(
            EmailCode.email == email,
            EmailCode.purpose == purpose,
            EmailCode.is_used == False,  # noqa: E712
        )
        .order_by(EmailCode.id.desc())
        .limit(1)
    )).scalar_one_or_none()

    if row is None:
        raise EmailCodeError("Код не найден. Запросите новый.")

    if datetime.now(timezone.utc) > _utc(row.expires_at):
        row.is_used = True
        await db.commit()
        raise EmailCodeError("Код истёк. Запросите новый.", status_code=410)

    row.attempts = (row.attempts or 0) + 1
    if hash_otp_code(code) != row.code_hash:
        if row.attempts >= MAX_ATTEMPTS:
            row.is_used = True
            await db.commit()
            logger.warning("Email code burned after %s attempts: %s",
                           row.attempts, email)
            raise EmailCodeError(
                "Слишком много попыток. Запросите новый код.",
                status_code=429,
            )
        await db.commit()
        raise EmailCodeError("Неверный код")

    row.is_used = True
    await db.commit()
    logger.info("Email code verified: email=%s purpose=%s", email, purpose)

"""«Подтвердить почту» — emailed codes for an account's own email contact.

The 1.79.0 contact model upgrades a contact to verified only when the value
is proven by a provider (social login) or by an emailed code; self-typing
never verifies. Password reset already stamps verified_via="code" as a side
effect — this module owns the explicit roundtrip («Подтвердить» next to an
unverified email):

- start(): issue a confirm_email code and send the letter;
- finish(): check the code and upgrade the contact to verified_via="code".

Callers own ownership checks (the contact row must belong to the current
account) and HTTP shapes; SMTP failures raise 503 so an explicit user
action never silently does nothing.
"""
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.user_contact import UserContact
from app.services import email_codes, mailer
from app.services.contacts import CONTACT_EMAIL, mark_verified

logger = get_logger(__name__)

EMAIL_VERIFY_PURPOSE = email_codes.PURPOSE_CONFIRM_EMAIL


def require_email_contact(contact: UserContact) -> None:
    """Only emails carry codes — phones are confirmed by MAX/social logins."""
    if contact.contact_type != CONTACT_EMAIL:
        raise HTTPException(
            status_code=400,
            detail="Код подтверждения приходит только на почту",
        )


async def start_email_verification(
    db: AsyncSession, contact: UserContact
) -> None:
    """Issue + send a fresh confirm code; raises 503 when nothing was sent."""
    code = await email_codes.issue_code(db, contact.value, EMAIL_VERIFY_PURPOSE)
    sent = await mailer.send_email_confirm_code(contact.value, code)
    logger.info("Contact confirm code: contact_id=%s sent=%s",
                contact.id, sent)
    if not sent:
        raise HTTPException(
            status_code=503,
            detail="Не удалось отправить письмо. Попробуйте позже.",
        )


async def finish_email_verification(
    db: AsyncSession, contact: UserContact, code: str
) -> UserContact:
    """Check the code and mark the contact verified (verified_via="code")."""
    try:
        await email_codes.verify_code(
            db, contact.value, EMAIL_VERIFY_PURPOSE, code)
    except email_codes.EmailCodeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail)
    await mark_verified(db, contact, via="code")
    await db.commit()
    return contact

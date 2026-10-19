"""User contacts service — phones/emails of an account, in one place.

Brain of the 1.79.0 contact model (см. LOCAL.md «Единый вход»):

- every value is stored normalized: phones via
  :func:`app.utils.phone.normalize_phone` ("+7 (XXX) XXX-XX-XX"), emails
  lowercased/stripped. All writers must go through this module so the unique
  (contact_type, value) index never sees two spellings of the same value.
- the unified login entry searches accounts by contact value; social logins
  attach their provider-confirmed contacts. A value already occupied by
  another account is TRANSFERRED here when transfer=True (audit-logged) —
  the agreed "телефон важнее почты, занятое значение переносим" rule.
- verification is monotonic: unverified -> "social" / "code", never back.
  Phone is confirmed by social logins only; email — by a social login or a
  code sent to that address.
- legacy users.phone / users.email columns stay for the transition: they are
  filled as an empty-only mirror (and cleared from a donor account when a
  value is transferred), so old screens keep working while everything new
  reads/writes contacts.
"""
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.user import User
from app.models.user_contact import UserContact
from app.services.audit import log_action
from app.utils.phone import normalize_phone

logger = get_logger(__name__)

CONTACT_PHONE = "phone"
CONTACT_EMAIL = "email"
CONTACT_TYPES = (CONTACT_PHONE, CONTACT_EMAIL)
VERIFIED_VIA_VALUES = ("social", "code")


class InvalidContact(ValueError):
    """Value can not be normalized to a phone / email."""


class ContactTaken(Exception):
    """Value belongs to another account and transfer was not allowed."""

    def __init__(self, contact: UserContact):
        super().__init__(
            f"{contact.contact_type} {contact.value} уже привязан "
            f"к аккаунту {contact.user_id}"
        )
        self.contact = contact


class ContactNotFound(Exception):
    """The user does not own a contact with this value."""


# ─── Normalization ────────────────────────────────────────────────────

def normalize_email(value: str) -> str:
    value = (value or "").strip().lower()
    if not value or "@" not in value or value.startswith("@") or value.endswith("@"):
        raise InvalidContact(f"Некорректный email: {value!r}")
    return value


def normalize_contact_value(contact_type: str, value: str) -> str:
    if contact_type == CONTACT_PHONE:
        try:
            return normalize_phone(value)
        except ValueError as exc:
            raise InvalidContact(str(exc)) from exc
    if contact_type == CONTACT_EMAIL:
        return normalize_email(value)
    raise InvalidContact(f"Неизвестный тип контакта: {contact_type!r}")


# ─── Lookup ───────────────────────────────────────────────────────────

async def get_by_value(
    db: AsyncSession, contact_type: str, value: str
) -> Optional[UserContact]:
    value = normalize_contact_value(contact_type, value)
    result = await db.execute(
        select(UserContact).where(
            UserContact.contact_type == contact_type,
            UserContact.value == value,
        )
    )
    return result.scalar_one_or_none()


async def find_user_by_contact(
    db: AsyncSession, contact_type: str, value: str,
    *, include_legacy: bool = True,
) -> Optional[User]:
    """Account owning this contact value (any verification state), or None.

    Invalid values are treated as "not found": entry forms surface their own
    validation errors, the search itself stays non-throwing.

    Transitional fallback: when no contact row matches, the legacy
    users.phone / users.email columns are checked — accounts created by
    paths that do not write contacts yet still resolve. The contact service
    keeps those columns coherent (mirror on write, cleared on
    transfer/removal), so a legacy match stays trustworthy while it lasts.
    """
    try:
        value = normalize_contact_value(contact_type, value)
    except InvalidContact:
        return None
    contact = (await db.execute(
        select(UserContact).where(
            UserContact.contact_type == contact_type,
            UserContact.value == value,
        )
    )).scalar_one_or_none()
    if contact is not None:
        return await db.get(User, contact.user_id)
    if not include_legacy:
        return None
    column = User.phone if contact_type == CONTACT_PHONE else User.email
    return (await db.execute(
        select(User).where(column == value)
    )).scalar_one_or_none()


async def get_contacts(db: AsyncSession, user_id: int) -> list[UserContact]:
    result = await db.execute(
        select(UserContact)
        .where(UserContact.user_id == user_id)
        .order_by(UserContact.contact_type,
                  UserContact.is_primary.desc(),
                  UserContact.id)
    )
    return list(result.scalars().all())


async def primary_contact(
    db: AsyncSession, user_id: int, contact_type: str
) -> Optional[UserContact]:
    """The primary contact of a type; falls back to the oldest one (read-only
    self-heal — the caller may persist the fallback by marking it primary)."""
    result = await db.execute(
        select(UserContact).where(
            UserContact.user_id == user_id,
            UserContact.contact_type == contact_type,
            UserContact.is_primary == True,  # noqa: E712
        ).limit(1)
    )
    contact = result.scalar_one_or_none()
    if contact is not None:
        return contact
    result = await db.execute(
        select(UserContact).where(
            UserContact.user_id == user_id,
            UserContact.contact_type == contact_type,
        ).order_by(UserContact.id).limit(1)
    )
    return result.scalar_one_or_none()


# ─── Mutations ────────────────────────────────────────────────────────

async def _clear_primary(
    db: AsyncSession, user_id: int, contact_type: str
) -> None:
    others = (await db.execute(
        select(UserContact).where(
            UserContact.user_id == user_id,
            UserContact.contact_type == contact_type,
            UserContact.is_primary == True,  # noqa: E712
        )
    )).scalars().all()
    for c in others:
        c.is_primary = False


async def _ensure_primary_position(
    db: AsyncSession, contact: UserContact, user_id: int, contact_type: str,
    make_primary: bool,
) -> bool:
    """Give the contact the primary slot when asked, or when the user has no
    primary of this type yet (first contact leads). Returns changed."""
    if contact.is_primary:
        return False
    if not make_primary:
        has_primary = (await db.execute(
            select(UserContact.id).where(
                UserContact.user_id == user_id,
                UserContact.contact_type == contact_type,
                UserContact.is_primary == True,  # noqa: E712
                UserContact.id != contact.id,
            ).limit(1)
        )).scalar_one_or_none()
        if has_primary is not None:
            return False
    await _clear_primary(db, user_id, contact_type)
    contact.is_primary = True
    return True


async def _has_contact(
    db: AsyncSession, user_id: int, contact_type: str, value: str
) -> bool:
    found = (await db.execute(
        select(UserContact.id).where(
            UserContact.user_id == user_id,
            UserContact.contact_type == contact_type,
            UserContact.value == value,
        ).limit(1)
    )).scalar_one_or_none()
    return found is not None


async def _mirror_legacy(
    db: AsyncSession, user: User, contact_type: str, value: str,
    *, confirmed: bool = False,
) -> None:
    """Fill the transitional users.phone / users.email column when it is
    empty and the value is not held by another account (both are UNIQUE).

    confirmed=True (provider-confirmed attach): a legacy column held by
    another account WITHOUT a contact row of its own is a stale pre-contact
    claim — it is cleared so the mirror follows the confirmed owner.
    """
    if contact_type == CONTACT_PHONE:
        if user.phone:
            return
        taken_user = (await db.execute(
            select(User).where(User.phone == value, User.id != user.id)
        )).scalar_one_or_none()
        if taken_user is None:
            user.phone = value
        elif confirmed and not await _has_contact(
                db, taken_user.id, contact_type, value):
            taken_user.phone = None
            await db.flush()  # free the UNIQUE value before we take it
            user.phone = value
            logger.info(
                "Legacy phone mirror re-pointed to confirmed owner: "
                "%s user_id=%s → %s", value, taken_user.id, user.id)
    elif contact_type == CONTACT_EMAIL:
        if user.email:
            return
        taken_user = (await db.execute(
            select(User).where(User.email == value, User.id != user.id)
        )).scalar_one_or_none()
        if taken_user is None:
            user.email = value
        elif confirmed and not await _has_contact(
                db, taken_user.id, contact_type, value):
            taken_user.email = None
            await db.flush()
            user.email = value
            logger.info(
                "Legacy email mirror re-pointed to confirmed owner: "
                "%s user_id=%s → %s", value, taken_user.id, user.id)


async def attach_contact(
    db: AsyncSession,
    user: User,
    contact_type: str,
    value: str,
    *,
    verified_via: Optional[str] = None,
    make_primary: bool = False,
    transfer: bool = False,
) -> tuple[UserContact, bool]:
    """Idempotently put ``value`` on ``user``; returns (contact, changed).

    - value is normalized first; invalid values raise InvalidContact;
    - if the value sits on ANOTHER account: transfer=False raises
      ContactTaken (callers surface "занят"), transfer=True moves the value
      here, audit-logs the transfer and clears the donor's legacy mirror;
    - verified_via ("social"/"code") upgrades the contact, never downgrades;
    - make_primary=True — or the user having no primary of this type yet —
      puts the contact into the primary slot.
    """
    if verified_via is not None and verified_via not in VERIFIED_VIA_VALUES:
        raise ValueError(f"Unsupported verified_via: {verified_via!r}")
    value = normalize_contact_value(contact_type, value)
    now = datetime.now(timezone.utc)
    changed = False

    contact = (await db.execute(
        select(UserContact).where(
            UserContact.contact_type == contact_type,
            UserContact.value == value,
        )
    )).scalar_one_or_none()

    if contact is None:
        contact = UserContact(
            user_id=user.id,
            contact_type=contact_type,
            value=value,
            is_verified=verified_via is not None,
            verified_via=verified_via,
            verified_at=now if verified_via else None,
        )
        db.add(contact)
        await db.flush()
        changed = True
    elif contact.user_id != user.id:
        if not transfer:
            raise ContactTaken(contact)
        donor_id = contact.user_id
        contact.user_id = user.id
        contact.is_primary = False
        donor = await db.get(User, donor_id)
        if donor is not None:
            if contact_type == CONTACT_PHONE and donor.phone == value:
                donor.phone = None
            elif contact_type == CONTACT_EMAIL and donor.email == value:
                donor.email = None
        logger.warning(
            "Contact transferred: %s %s from user_id=%s to user_id=%s",
            contact_type, value, donor_id, user.id,
        )
        await log_action(
            db, user.id, "contact_transfer", "user_contact", contact.id,
            f"{contact_type} {value}: аккаунт {donor_id} → {user.id}",
            level="warning",
        )
        changed = True

    if verified_via and not contact.is_verified:
        contact.is_verified = True
        contact.verified_via = verified_via
        contact.verified_at = contact.verified_at or now
        changed = True

    if await _ensure_primary_position(
            db, contact, user.id, contact_type, make_primary):
        changed = True

    await _mirror_legacy(db, user, contact_type, value, confirmed=transfer)
    return contact, changed


async def set_primary(
    db: AsyncSession, user: User, contact_type: str, value: str
) -> UserContact:
    """Make the user's own contact primary (raises ContactNotFound)."""
    contact = await get_by_value(db, contact_type, value)
    if contact is None or contact.user_id != user.id:
        raise ContactNotFound(
            f"{contact_type} {value} не найден у аккаунта {user.id}"
        )
    if not contact.is_primary:
        await _clear_primary(db, user.id, contact_type)
        contact.is_primary = True
    return contact


async def remove_contact(
    db: AsyncSession, user: User, contact_type: str, value: str
) -> bool:
    """Detach a contact from the user. Promotes another contact of the type
    into the primary slot if the removed one was primary. Clears the legacy
    mirror when it pointed at the removed value. Returns True when removed."""
    contact = await get_by_value(db, contact_type, value)
    if contact is None or contact.user_id != user.id:
        return False
    removed_value = contact.value
    was_primary = bool(contact.is_primary)
    await db.delete(contact)
    await db.flush()
    if contact_type == CONTACT_PHONE and user.phone == removed_value:
        user.phone = None
    elif contact_type == CONTACT_EMAIL and user.email == removed_value:
        user.email = None
    if was_primary:
        fallback = (await db.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == contact_type,
            ).order_by(UserContact.id).limit(1)
        )).scalar_one_or_none()
        if fallback is not None:
            fallback.is_primary = True
    return True


async def mark_verified(
    db: AsyncSession, contact: UserContact, via: str = "code"
) -> bool:
    """Upgrade a contact to verified (monotonic). Returns changed."""
    if via not in VERIFIED_VIA_VALUES:
        raise ValueError(f"Unsupported verified_via: {via!r}")
    if contact.is_verified:
        return False
    contact.is_verified = True
    contact.verified_via = via
    contact.verified_at = datetime.now(timezone.utc)
    return True

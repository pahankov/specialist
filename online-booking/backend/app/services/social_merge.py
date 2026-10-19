"""Social login service: profile merge + account resolution (VK / Yandex / MAX).

Policy (agreed, LOCAL.md «Единый вход»):

- account lookup order: provider social id → provider-confirmed phone →
  provider-confirmed email → create. Self-reported data never matches an
  account (a typed vCard email must not log anyone into someone else's row).
- provider-confirmed contacts are attached with verified_via="social"; a
  value occupied by another account is TRANSFERRED to the chosen account
  (audit-logged) — the provider's vouch beats a stored claim. Self-reported
  contacts are attached unverified and skipped when already taken.
- name / avatar: fill what is empty, refresh what a social login set
  (name_source is a provider id); a human-set name is never overwritten.
- consent (152-FZ): stamped on creation, backfilled when missing.
- legacy users.is_verified is no longer written here — verification lives
  on contacts now (the column stays readable during the transition).

The caller finishes with :func:`complete_social_login` to mint the JWT.
"""
from datetime import datetime, timezone as dt_timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.services.contacts import (
    CONTACT_EMAIL,
    CONTACT_PHONE,
    ContactTaken,
    InvalidContact,
    attach_contact,
    find_user_by_contact,
)
from app.services.names import compose_full_name
from app.utils.tokens import create_access_token, create_refresh_token_payload

logger = get_logger(__name__)

# name_source values that mean "a social login set this name" — any of them
# may be refreshed by a later social login. Anything else ("user"/NULL) is a
# human-set name and is left alone.
SOCIAL_NAME_SOURCES = ("vk", "yandex", "max")


async def merge_social_profile(
    db: AsyncSession,
    user: User,
    *,
    provider: str,
    first_name: str = "",
    last_name: str = "",
    avatar_url: Optional[str] = None,
) -> bool:
    """Fill-if-empty name/avatar merge for one social login. Returns changed.

    Contacts are NOT touched here — the contact service handles phones and
    emails (attach/verify/transfer); this function only owns name+avatar.
    """
    changed = False

    # ── name / last_name ────────────────────────────────────────────────
    first = (first_name or "").strip()
    last = (last_name or "").strip()
    social_name = compose_full_name(first, last) if (first or last) else ""
    may_set_name = not user.name or user.name_source in SOCIAL_NAME_SOURCES
    if social_name and may_set_name:
        if social_name != user.name or (last or None) != user.last_name:
            user.name = social_name
            user.last_name = last or None
            user.name_source = provider
            changed = True

    # ── avatar (latest social login that has one wins) ──────────────────
    if avatar_url and user.avatar_url != avatar_url:
        user.avatar_url = avatar_url
        changed = True

    return changed


async def _attach_provider_contact(
    db: AsyncSession,
    user: User,
    contact_type: str,
    value: str,
    *,
    confirmed: bool,
) -> None:
    """Put a provider contact on the account (transfer only when confirmed).

    Unconfirmed values (e.g. a MAX vCard email) are attached unverified and
    skipped when another account holds them — never stolen, never a lookup
    key. Confirmed values may transfer; attach_contact audit-logs that.
    """
    try:
        await attach_contact(
            db, user, contact_type, value,
            verified_via=("social" if confirmed else None),
            transfer=confirmed,
        )
    except ContactTaken:
        logger.info(
            "Social login: %s %s already belongs to another account, "
            "skipped (user_id=%s)", contact_type, value, user.id,
        )
    except InvalidContact:
        logger.info("Social login: invalid %s %r ignored (user_id=%s)",
                    contact_type, value, user.id)


async def _apply_link_fields(
    user: User, fields: Optional[dict], *, only_empty: bool,
) -> bool:
    """Set provider-specific bindings (vk/yandex/max ids, max username).

    Existing values are never overwritten (only_empty=True): the first login
    fixes the binding, later logins only fill gaps.
    """
    changed = False
    for attr, value in (fields or {}).items():
        if value is None:
            continue
        if only_empty and getattr(user, attr) is not None:
            continue
        if getattr(user, attr) != value:
            setattr(user, attr, value)
            changed = True
    return changed


async def resolve_social_user(
    db: AsyncSession,
    *,
    provider: str,
    social_id: Optional[int],
    social_field: Optional[str],
    first_name: str = "",
    last_name: str = "",
    phone: Optional[str] = None,
    phone_confirmed: bool = False,
    email: Optional[str] = None,
    email_confirmed: bool = False,
    avatar_url: Optional[str] = None,
    fallback_name: str = "Соц. Пользователь",
    consent: bool = False,
    link_fields: Optional[dict] = None,
    defer_creation: bool = False,
) -> tuple[User, bool]:
    """Find the account behind a social login or create one → (user, is_new).

    See the module docstring for the lookup order and the contact policy.
    Raises 403 for a blocked account; never logs anyone in blind.

    When ``defer_creation=True`` (1.80.0, 152-FZ consent flow), a new user
    is built but NOT committed — the frontend shows ConsentScreen, then
    calls /auth/consent/complete which commits with consent stamped.
    """
    from app.modules.auth.service import OFFER_VERSION, POLICY_VERSION

    now = datetime.now(dt_timezone.utc)
    user: Optional[User] = None

    if social_field and social_id is not None:
        col = getattr(User, social_field)
        user = (await db.execute(
            select(User).where(col == social_id))).scalar_one_or_none()

    if user is None and phone and phone_confirmed:
        user = await find_user_by_contact(db, CONTACT_PHONE, phone)

    if user is None and email and email_confirmed:
        user = await find_user_by_contact(db, CONTACT_EMAIL, email)

    is_new = user is None
    if is_new:
        first = (first_name or "").strip()
        last = (last_name or "").strip()
        name_from_provider = bool(first or last)
        user = User(
            name=compose_full_name(first, last) or fallback_name,
            last_name=(last or None),
            role=UserRole.CLIENT,
            hashed_password=None,  # social-only auth (same as OTP/MAX paths)
            avatar_url=avatar_url,
            # name came from the provider: a later social login may refresh
            # it, a human edit ("user") will not be overwritten.
            name_source=(provider if name_from_provider else None),
            # 152-FZ: consent checkbox on the social login form.
            consent_at=(now if consent else None),
            consent_policy_version=POLICY_VERSION if consent else None,
            consent_offer_version=OFFER_VERSION if consent else None,
        )
        if social_field and social_id is not None:
            setattr(user, social_field, social_id)
        await _apply_link_fields(user, link_fields, only_empty=False)
        db.add(user)
        if defer_creation:
            # Don't commit — the frontend will call /auth/consent/complete.
            logger.info("Deferred user creation via %s: user_id=%s (pending consent)", provider, user.id)
            return user, True
        await db.flush()
        from app.services.clients import get_or_create_profile
        await get_or_create_profile(db, user)
        logger.info("New client created via %s: user_id=%s", provider, user.id)
    else:
        if user.is_active is False:
            raise HTTPException(status_code=403, detail="Аккаунт заблокирован.")
        changed = False
        if (social_field and social_id is not None
                and getattr(user, social_field) != social_id):
            setattr(user, social_field, social_id)
            changed = True
        linked = await _apply_link_fields(user, link_fields, only_empty=True)
        changed = changed or linked
        merged = await merge_social_profile(
            db, user, provider=provider,
            first_name=first_name, last_name=last_name,
            avatar_url=avatar_url,
        )
        changed = changed or merged
        if consent and user.consent_at is None:
            # Backfill consent for accounts created before consent tracking.
            user.consent_at = now
            user.consent_policy_version = POLICY_VERSION
            user.consent_offer_version = OFFER_VERSION
            changed = True
        if changed:
            await db.commit()
        logger.info("Linked %s login to existing user_id=%s", provider, user.id)

    # ── contacts land on the chosen account (кроме соц-id всё через сервис) ──
    if phone:
        await _attach_provider_contact(db, user, CONTACT_PHONE, phone,
                                       confirmed=phone_confirmed)
    if email:
        await _attach_provider_contact(db, user, CONTACT_EMAIL, email,
                                       confirmed=email_confirmed)

    return user, is_new


async def complete_social_login(db: AsyncSession, user: User) -> str:
    """Mint the JWT session for a resolved social user (commit included)."""
    access_token = create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "is_admin": user.role == UserRole.ADMIN,
    })
    refresh_value, expires_at = create_refresh_token_payload(
        user.id, user.email or "")
    db.add(RefreshToken(user_id=user.id, token=refresh_value,
                        expires_at=expires_at))
    await db.commit()
    return access_token


async def bind_social_login(
    db: AsyncSession,
    *,
    user_id: int,
    provider: str,
    social_id: int,
    social_field: str,
    link_fields: Optional[dict] = None,
    first_name: str = "",
    last_name: str = "",
    phone: Optional[str] = None,
    phone_confirmed: bool = False,
    email: Optional[str] = None,
    email_confirmed: bool = False,
    avatar_url: Optional[str] = None,
) -> User:
    """«Привязать» flow: link a social profile to the CURRENT account.

    The account is fixed by the user id inside the signed start state — the
    profile is deliberately NOT re-resolved by phone/email (that could fork
    a new account or steal a different one). Conflicts are hard errors:
    a social id already bound elsewhere (409) or a different profile of the
    same provider already on this account (409).
    """
    user = await db.get(User, user_id)
    if user is None or user.is_active is False:
        raise HTTPException(status_code=403, detail="Аккаунт недоступен")

    col = getattr(User, social_field)
    other = (await db.execute(
        select(User).where(col == social_id))).scalar_one_or_none()
    if other is not None and other.id != user.id:
        raise HTTPException(
            status_code=409,
            detail="Этот профиль уже привязан к другому аккаунту. "
                   "Войдите через соцсеть, чтобы пользоваться им.",
        )
    bound = getattr(user, social_field)
    if bound is not None and bound != social_id:
        raise HTTPException(
            status_code=409,
            detail="У аккаунта уже привязан другой профиль этой соцсети.",
        )

    setattr(user, social_field, social_id)
    await _apply_link_fields(user, link_fields, only_empty=True)
    await merge_social_profile(
        db, user, provider=provider,
        first_name=first_name, last_name=last_name, avatar_url=avatar_url,
    )
    if phone:
        await _attach_provider_contact(db, user, CONTACT_PHONE, phone,
                                       confirmed=phone_confirmed)
    if email:
        await _attach_provider_contact(db, user, CONTACT_EMAIL, email,
                                       confirmed=email_confirmed)
    await db.commit()
    logger.info("Social profile linked: provider=%s user_id=%s",
                provider, user.id)
    return user

"""Shared master-profile serialization and self-activation readiness.

The master panel and the client-side draft («Стать мастером») must show
exactly the same profile data, otherwise the reused form drifts. This
module is the single place that builds that payload and decides whether
the profile is ready to become an active master.
"""
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.city import City
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.user import User
from app.models.user_contact import UserContact
from app.services.addresses import has_house_number
from app.services.contacts import CONTACT_EMAIL, CONTACT_PHONE, get_contacts
from app.services.names import split_full_name


def contact_out(contact: UserContact) -> dict:
    """Serialize one own contact (verify flags included)."""
    return {
        "id": contact.id,
        "contact_type": contact.contact_type,
        "value": contact.value,
        "is_verified": bool(contact.is_verified),
        "verified_via": contact.verified_via,
        "is_primary": bool(contact.is_primary),
    }


def _has_verified_email(contacts: list[UserContact]) -> bool:
    """Only an actually verified email counts.

    The owner's review: the old checklist showed a green tick for merely
    having an email row. A social login or an emailed code must have
    confirmed it; the legacy users.is_verified flag is not enough.
    """
    return any(
        contact.contact_type == CONTACT_EMAIL and bool(contact.is_verified)
        for contact in contacts
    )


def _has_phone(user: User, contacts: list[UserContact]) -> bool:
    return bool(user.phone) or any(
        contact.contact_type == CONTACT_PHONE for contact in contacts
    )


def _has_social(user: User) -> bool:
    return (
        user.vk_user_id is not None
        or user.yandex_user_id is not None
        or user.max_user_id is not None
    )


async def master_profile_snapshot(
    db: AsyncSession,
    user: User,
    master_profile: Optional[MasterProfile] = None,
    *,
    client_address_fallback: bool = False,
) -> tuple[dict, dict]:
    """Return ``(profile payload, readiness checklist)`` for a user.

    ``master_profile`` may be None (a client who has not opened the draft
    yet). In that case the form still gets the user's name, contacts,
    social flags and social avatar so it can be prefilled.

    ``client_address_fallback`` is used only by the draft GET: the client
    cabinet already stores a home address, and the owner expects it to
    prefill the cabinet-address field. The saved draft address always wins;
    the fallback is just for an empty draft field.
    """
    city_name = None
    if user.city_id:
        city_name = (await db.execute(
            select(City.name_ru).where(City.id == user.city_id)
        )).scalar_one_or_none()

    contacts = await get_contacts(db, user.id)
    mp = master_profile

    cabinet_address = mp.cabinet_address if mp is not None else None
    if client_address_fallback and not (cabinet_address or "").strip():
        # The client cabinet already stores a home address. Use it until the
        # draft gets its own cabinet address, so the field is not empty on
        # the first visit (including drafts saved before this fix).
        cabinet_address = (await db.execute(
            select(ClientProfile.address).where(ClientProfile.user_id == user.id)
        )).scalar_one_or_none()

    avatar_preset = mp.avatar_preset if mp is not None else None
    avatar_url = mp.avatar_url if mp is not None else None
    # Social avatar is the default until the master uploads a photo or
    # picks an emoji preset. The draft form shows it immediately; activation
    # persists it if the API was called without an explicit avatar.
    if not avatar_url and not avatar_preset:
        avatar_url = user.avatar_url

    profile = {
        "id": user.id,
        "name": user.name,
        "last_name": user.last_name,
        "city_id": user.city_id,
        "city_name": city_name,
        "phone": user.phone,
        "email": user.email,
        "has_password": user.hashed_password is not None,
        "vk_bound": user.vk_user_id is not None,
        "yandex_bound": user.yandex_user_id is not None,
        "max_bound": user.max_user_id is not None,
        "max_username": user.max_username,
        "contacts": [contact_out(contact) for contact in contacts],
        "telegram_username": mp.telegram_username if mp is not None else None,
        "description": mp.description if mp is not None else None,
        "avatar_url": avatar_url,
        "avatar_preset": avatar_preset,
        "experience_years": mp.experience_years if mp is not None else None,
        "cabinet_address": cabinet_address,
        "certificates": (mp.certificates or []) if mp is not None else [],
        "auto_confirm": bool(mp.auto_confirm) if mp is not None else False,
        "auto_complete": bool(mp.auto_complete) if mp is not None else False,
        "prefer_master_cabinet": (
            bool(mp.prefer_master_cabinet) if mp is not None else True
        ),
        "profile_id": mp.id if mp is not None else None,
        "tariff": (mp.tariff or "trial") if mp is not None else None,
        "trial_ends_at": (
            mp.trial_ends_at.isoformat()
            if mp is not None and mp.trial_ends_at else None
        ),
    }

    # Require a real first + last name. A single-word display name is not
    # enough even if it was copied into last_name by set_names().
    first_name, name_rest = split_full_name(user.name)
    readiness = {
        "names": bool(first_name and name_rest),
        "cabinet_address": has_house_number(cabinet_address),
        "phone": _has_phone(user, contacts),
        "verified_email": _has_verified_email(contacts),
        "social": _has_social(user),
    }
    return profile, readiness

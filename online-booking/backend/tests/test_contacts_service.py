"""Tests for app.services.contacts — the 1.79.0 contact model."""
import pytest
from sqlalchemy import select

from app.models.audit_log import AuditLog
from app.models.user import User, UserRole
from app.services.contacts import (
    CONTACT_EMAIL,
    CONTACT_PHONE,
    ContactNotFound,
    ContactTaken,
    InvalidContact,
    attach_contact,
    find_user_by_contact,
    get_contacts,
    mark_verified,
    normalize_contact_value,
    primary_contact,
    remove_contact,
    set_primary,
)


async def _make_user(session, name="UC User", **kwargs):
    user = User(name=name, role=UserRole.CLIENT, **kwargs)
    session.add(user)
    await session.flush()
    return user


# ─── Normalization ────────────────────────────────────────────────────

def test_normalize_contact_value():
    assert normalize_contact_value(CONTACT_PHONE, "8 (916) 555-44-33") == "+7 (916) 555-44-33"
    assert normalize_contact_value(CONTACT_PHONE, "79165554433") == "+7 (916) 555-44-33"
    assert normalize_contact_value(CONTACT_PHONE, "+7 916 555 44 33") == "+7 (916) 555-44-33"
    assert normalize_contact_value(CONTACT_EMAIL, "  A@Mail.RU ") == "a@mail.ru"

    with pytest.raises(InvalidContact):
        normalize_contact_value(CONTACT_EMAIL, "not-an-email")
    with pytest.raises(InvalidContact):
        normalize_contact_value(CONTACT_PHONE, "12")
    with pytest.raises(InvalidContact):
        normalize_contact_value("telegram", "x")


# ─── Attach / verify / primary ────────────────────────────────────────

async def test_attach_new_contact_is_primary_and_mirrors_legacy(session):
    user = await _make_user(session)

    contact, changed = await attach_contact(
        session, user, CONTACT_PHONE, "8 916 000-00-01")

    assert changed is True
    assert contact.value == "+7 (916) 000-00-01"
    assert contact.is_verified is False
    assert contact.verified_via is None
    assert contact.is_primary is True
    assert user.phone == "+7 (916) 000-00-01"  # legacy mirror for old screens
    assert user.email is None


async def test_find_user_by_contact_falls_back_to_legacy_column(session):
    """Transition: accounts with only users.email/users.phone still resolve."""
    legacy = await _make_user(session, name="Legacy", email="legacy@example.com")

    found = await find_user_by_contact(
        session, CONTACT_EMAIL, " Legacy@Example.COM ")
    assert found is not None and found.id == legacy.id

    # include_legacy=False sees contacts only.
    assert await find_user_by_contact(
        session, CONTACT_EMAIL, "legacy@example.com",
        include_legacy=False) is None


async def test_confirmed_attach_repoints_stale_legacy_claim(session):
    """A provider-confirmed value wins over a legacy-only claim elsewhere."""
    owner = await _make_user(session, name="Owner", phone="+7 (900) 111-22-33")
    newcomer = await _make_user(session, name="Newcomer")
    await session.commit()

    contact, _ = await attach_contact(
        session, newcomer, CONTACT_PHONE, "89001112233",
        verified_via="social", transfer=True)
    await session.commit()

    await session.refresh(owner)
    await session.refresh(newcomer)
    assert owner.phone is None  # stale pre-contact claim cleared
    assert newcomer.phone == "+7 (900) 111-22-33"  # mirror followed
    assert contact.user_id == newcomer.id


async def test_second_contact_of_type_is_not_primary(session):
    user = await _make_user(session)
    first, _ = await attach_contact(session, user, CONTACT_EMAIL, "first@mail.ru")
    second, _ = await attach_contact(session, user, CONTACT_EMAIL, "second@mail.ru")

    assert first.is_primary is True
    assert second.is_primary is False


async def test_attach_is_idempotent_and_verification_monotonic(session):
    user = await _make_user(session)
    contact, changed = await attach_contact(
        session, user, CONTACT_EMAIL, "a@mail.ru")
    assert changed is True and contact.is_verified is False

    # Same value in different spelling: no duplicate, no change.
    same, changed = await attach_contact(
        session, user, CONTACT_EMAIL, "  A@MAIL.RU ")
    assert changed is False
    assert same.id == contact.id
    assert len(await get_contacts(session, user.id)) == 1

    # Provider confirms the email: upgrade to "social".
    updated, changed = await attach_contact(
        session, user, CONTACT_EMAIL, "a@mail.ru", verified_via="social")
    assert changed is True
    assert updated.is_verified is True
    assert updated.verified_via == "social"

    # Re-attaching without confirmation never downgrades.
    kept, changed = await attach_contact(
        session, user, CONTACT_EMAIL, "a@mail.ru")
    assert changed is False
    assert kept.is_verified is True and kept.verified_via == "social"


async def test_attach_marks_first_social_contact_verified(session):
    user = await _make_user(session)
    contact, _ = await attach_contact(
        session, user, CONTACT_PHONE, "+79160000002", verified_via="social")

    assert contact.is_verified is True
    assert contact.verified_via == "social"
    assert contact.verified_at is not None


async def test_attach_taken_without_transfer_raises(session):
    owner = await _make_user(session, name="Owner")
    other = await _make_user(session, name="Other")
    await attach_contact(session, owner, CONTACT_PHONE, "+79160000003")

    with pytest.raises(ContactTaken):
        await attach_contact(session, other, CONTACT_PHONE, "89160000003")

    assert len(await get_contacts(session, other.id)) == 0


async def test_attach_transfer_moves_value_and_logs(session):
    donor = await _make_user(session, name="Donor")
    donor_contact, _ = await attach_contact(
        session, donor, CONTACT_PHONE, "8 916 000-00-05", verified_via="code")
    assert donor.phone == "+7 (916) 000-00-05"

    recipient = await _make_user(session, name="Recipient")
    moved, changed = await attach_contact(
        session, recipient, CONTACT_PHONE, "+79160000005",
        transfer=True, verified_via="social")

    assert changed is True
    assert moved.id == donor_contact.id
    assert moved.user_id == recipient.id
    # Monotonic: "code" is not downgraded to "social".
    assert moved.is_verified is True and moved.verified_via == "code"
    assert moved.is_primary is True  # recipient had no phones before
    assert donor.phone is None  # stale legacy mirror cleared
    assert recipient.phone == "+7 (916) 000-00-05"  # mirror filled

    logs = (await session.execute(
        select(AuditLog).where(AuditLog.action == "contact_transfer")
    )).scalars().all()
    assert len(logs) == 1
    assert "+7 (916) 000-00-05" in logs[0].details
    assert str(donor.id) in logs[0].details and str(recipient.id) in logs[0].details


async def test_set_primary_switches_within_own_contacts(session):
    user = await _make_user(session)
    first, _ = await attach_contact(session, user, CONTACT_EMAIL, "one@mail.ru")
    second, _ = await attach_contact(session, user, CONTACT_EMAIL, "two@mail.ru")

    result = await set_primary(session, user, CONTACT_EMAIL, "two@mail.ru")

    assert result.id == second.id
    assert result.is_primary is True
    assert first.is_primary is False
    lead = await primary_contact(session, user.id, CONTACT_EMAIL)
    assert lead.id == second.id

    # make_primary on attach also switches the slot.
    third, _ = await attach_contact(
        session, user, CONTACT_EMAIL, "three@mail.ru", make_primary=True)
    assert third.is_primary is True
    assert second.is_primary is False


async def test_set_primary_foreign_contact_raises(session):
    owner = await _make_user(session, name="Owner")
    stranger = await _make_user(session, name="Stranger")
    await attach_contact(session, owner, CONTACT_EMAIL, "owned@mail.ru")

    with pytest.raises(ContactNotFound):
        await set_primary(session, stranger, CONTACT_EMAIL, "owned@mail.ru")
    with pytest.raises(ContactNotFound):
        await set_primary(session, stranger, CONTACT_EMAIL, "ghost@mail.ru")


async def test_remove_contact_promotes_fallback_and_clears_mirror(session):
    user = await _make_user(session)
    first, _ = await attach_contact(session, user, CONTACT_EMAIL, "one@mail.ru")
    second, _ = await attach_contact(session, user, CONTACT_EMAIL, "two@mail.ru")
    assert user.email == "one@mail.ru"

    assert await remove_contact(session, user, CONTACT_EMAIL, "one@mail.ru") is True
    assert user.email is None
    assert second.is_primary is True  # fallback promotion

    assert await remove_contact(session, user, CONTACT_EMAIL, "ghost@mail.ru") is False
    contacts = await get_contacts(session, user.id)
    assert [c.value for c in contacts] == ["two@mail.ru"]


async def test_mark_verified_is_monotonic(session):
    user = await _make_user(session)
    contact, _ = await attach_contact(session, user, CONTACT_EMAIL, "code@mail.ru")

    assert await mark_verified(session, contact, via="code") is True
    assert contact.is_verified is True
    assert contact.verified_via == "code"
    assert contact.verified_at is not None
    assert await mark_verified(session, contact, via="code") is False


# ─── Lookup ───────────────────────────────────────────────────────────

async def test_find_user_by_contact_normalizes_and_misses(session):
    user = await _make_user(session)
    await attach_contact(session, user, CONTACT_PHONE, "+7 (961) 520-23-11")

    found = await find_user_by_contact(session, CONTACT_PHONE, "89615202311")
    assert found is not None and found.id == user.id

    assert await find_user_by_contact(session, CONTACT_PHONE, "89160000000") is None
    # Invalid values are treated as "not found", not an error.
    assert await find_user_by_contact(session, CONTACT_EMAIL, "broken") is None
    assert await find_user_by_contact(session, CONTACT_PHONE, "1") is None

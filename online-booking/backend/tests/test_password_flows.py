"""Tests for the 1.79.0 password flows: change, forgot-by-email, reset."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.email_code import EmailCode
from app.models.refresh_token import RefreshToken
from app.models.user import User, UserRole
from app.models.user_contact import UserContact
from app.modules.auth.token import create_access_token
from app.services import email_codes, mailer
from app.services.contacts import CONTACT_EMAIL, attach_contact
from app.utils.security import hash_password, verify_password


@pytest.fixture
async def pw_user(session):
    """Client with a password and a primary email contact."""
    user = User(
        name="Pw User",
        email="pw@example.com",
        phone="+7 (999) 000-77-11",
        hashed_password=hash_password("OldPass123!"),
        role=UserRole.CLIENT,
        is_active=True,
    )
    session.add(user)
    await session.flush()
    await attach_contact(session, user, CONTACT_EMAIL, "pw@example.com",
                         make_primary=True)
    await session.commit()
    token = create_access_token({
        "sub": str(user.id), "role": "CLIENT", "name": user.name,
        "is_admin": False,
    })
    return user.id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def sent_codes(monkeypatch):
    """Capture codes "sent" by the mailer instead of hitting SMTP."""
    captured = {}

    async def fake_reset(to, code):
        captured[to] = code
        return True

    monkeypatch.setattr(mailer, "send_password_reset_code", fake_reset)
    return captured


# ─── Change password ─────────────────────────────────────────────────

async def test_change_password_happy_path(client, session, pw_user):
    user_id, headers = pw_user
    resp = await client.post(
        "/api/v1/auth/password/change", headers=headers,
        json={"current_password": "OldPass123!",
              "new_password": "NewPass456!"},
    )
    assert resp.status_code == 200, resp.text

    user = await session.get(User, user_id)
    assert verify_password("NewPass456!", user.hashed_password)

    login = await client.post(
        "/api/v1/auth/login-unified",
        json={"identifier": "pw@example.com", "password": "NewPass456!"})
    assert login.status_code == 200

    old = await client.post(
        "/api/v1/auth/login-unified",
        json={"identifier": "pw@example.com", "password": "OldPass123!"})
    assert old.status_code == 401


async def test_change_password_wrong_current(client, pw_user):
    _, headers = pw_user
    resp = await client.post(
        "/api/v1/auth/password/change", headers=headers,
        json={"current_password": "WrongPass1!",
              "new_password": "NewPass456!"},
    )
    assert resp.status_code == 400
    assert "текущий" in resp.json()["detail"]


async def test_change_password_same_as_current(client, pw_user):
    _, headers = pw_user
    resp = await client.post(
        "/api/v1/auth/password/change", headers=headers,
        json={"current_password": "OldPass123!",
              "new_password": "OldPass123!"},
    )
    assert resp.status_code == 400


async def test_change_password_weak_new(client, pw_user):
    _, headers = pw_user
    resp = await client.post(
        "/api/v1/auth/password/change", headers=headers,
        json={"current_password": "OldPass123!", "new_password": "short"},
    )
    assert resp.status_code == 422


async def test_change_password_requires_existing_password(client, session):
    user = User(name="Soc User", email="soc@example.com",
                hashed_password=None, role=UserRole.CLIENT)
    session.add(user)
    await session.commit()
    token = create_access_token({
        "sub": str(user.id), "role": "CLIENT", "name": user.name,
        "is_admin": False,
    })
    resp = await client.post(
        "/api/v1/auth/password/change",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": "Whatever123!",
              "new_password": "NewPass456!"},
    )
    assert resp.status_code == 400
    assert "соцсет" in resp.json()["detail"]


# ─── Forgot («Забыли пароль») ────────────────────────────────────────

async def test_forgot_unknown_email_is_generic(client, session):
    resp = await client.post("/api/v1/auth/password/forgot",
                             json={"email": "ghost@example.com"})
    assert resp.status_code == 200
    assert "отправили код" in resp.json()["message"]
    rows = (await session.execute(select(EmailCode))).scalars().all()
    assert rows == []


async def test_forgot_sends_code_to_known_email(client, session, pw_user,
                                                sent_codes):
    resp = await client.post("/api/v1/auth/password/forgot",
                             json={"email": "PW@example.com"})
    assert resp.status_code == 200
    assert "pw@example.com" in sent_codes

    row = (await session.execute(
        select(EmailCode).where(EmailCode.email == "pw@example.com")
    )).scalar_one()
    assert row.purpose == email_codes.PURPOSE_RESET_PASSWORD
    assert row.is_used is False
    assert row.attempts == 0


# ─── Reset ───────────────────────────────────────────────────────────

async def test_reset_password_happy_path(client, session, pw_user,
                                         sent_codes):
    user_id, _ = pw_user
    session.add(RefreshToken(
        user_id=user_id, token="session-before-reset",
        expires_at=datetime.now(timezone.utc) + timedelta(days=30)))
    await session.commit()

    await client.post("/api/v1/auth/password/forgot",
                      json={"email": "pw@example.com"})
    code = sent_codes["pw@example.com"]

    resp = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": "pw@example.com", "code": code,
              "new_password": "ResetPass789!"})
    assert resp.status_code == 200, resp.text
    assert resp.json()["access_token"]

    user = await session.get(User, user_id)
    assert verify_password("ResetPass789!", user.hashed_password)

    # Every old session is revoked; the reset itself issued one fresh one.
    tokens = (await session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )).scalars().all()
    by_value = {t.token: t for t in tokens}
    assert by_value["session-before-reset"].is_revoked is True
    assert len([t for t in tokens if not t.is_revoked]) == 1

    # The code is single-use.
    again = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": "pw@example.com", "code": code,
              "new_password": "ResetPass789!"})
    assert again.status_code == 400

    old = await client.post(
        "/api/v1/auth/login-unified",
        json={"identifier": "pw@example.com", "password": "OldPass123!"})
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/auth/login-unified",
        json={"identifier": "pw@example.com", "password": "ResetPass789!"})
    assert new.status_code == 200


async def test_reset_wrong_code_burns_attempts(client, pw_user, sent_codes):
    await client.post("/api/v1/auth/password/forgot",
                      json={"email": "pw@example.com"})
    code = sent_codes["pw@example.com"]
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(4):
        resp = await client.post(
            "/api/v1/auth/password/reset",
            json={"email": "pw@example.com", "code": wrong,
                  "new_password": "ResetPass789!"})
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Неверный код"

    resp = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": "pw@example.com", "code": wrong,
              "new_password": "ResetPass789!"})
    assert resp.status_code == 429

    # Burned: even the correct code is gone now.
    resp = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": "pw@example.com", "code": code,
              "new_password": "ResetPass789!"})
    assert resp.status_code == 400
    assert "не найден" in resp.json()["detail"].lower()


async def test_reset_unknown_email_rejected(client):
    resp = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": "ghost@example.com", "code": "123456",
              "new_password": "ResetPass789!"})
    assert resp.status_code == 400


async def test_reset_verifies_email_contact(client, session, pw_user,
                                            sent_codes):
    """The emailed code proves the address — contact upgraded to code-level."""
    from app.models.user_contact import UserContact

    user_id, _ = pw_user
    contact = (await session.execute(
        select(UserContact).where(
            UserContact.user_id == user_id,
            UserContact.contact_type == "email",
        )
    )).scalar_one()
    assert contact.is_verified is False  # py-created account, never verified

    await client.post("/api/v1/auth/password/forgot",
                      json={"email": "pw@example.com"})
    resp = await client.post(
        "/api/v1/auth/password/reset",
        json={"email": "pw@example.com", "code": sent_codes["pw@example.com"],
              "new_password": "ResetPass789!"})
    assert resp.status_code == 200, resp.text

    await session.refresh(contact)
    assert contact.is_verified is True
    assert contact.verified_via == "code"


# ─── Email codes service ─────────────────────────────────────────────

async def test_code_reissue_burns_previous(session):
    first = await email_codes.issue_code(
        session, "re@example.com", email_codes.PURPOSE_RESET_PASSWORD)
    second = await email_codes.issue_code(
        session, "re@example.com", email_codes.PURPOSE_RESET_PASSWORD)

    with pytest.raises(email_codes.EmailCodeError):
        await email_codes.verify_code(
            session, "re@example.com",
            email_codes.PURPOSE_RESET_PASSWORD, first)
    await email_codes.verify_code(
        session, "re@example.com", email_codes.PURPOSE_RESET_PASSWORD, second)
    with pytest.raises(email_codes.EmailCodeError):
        await email_codes.verify_code(
            session, "re@example.com",
            email_codes.PURPOSE_RESET_PASSWORD, second)


async def test_expired_code_rejected(session):
    code = await email_codes.issue_code(
        session, "exp@example.com", email_codes.PURPOSE_RESET_PASSWORD)
    row = (await session.execute(
        select(EmailCode).where(EmailCode.email == "exp@example.com")
    )).scalar_one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    await session.commit()

    with pytest.raises(email_codes.EmailCodeError) as err:
        await email_codes.verify_code(
            session, "exp@example.com",
            email_codes.PURPOSE_RESET_PASSWORD, code)
    assert err.value.status_code == 410


# ─── Registration hook ───────────────────────────────────────────────

async def test_register_unified_creates_primary_phone_contact(client, session):
    resp = await client.post(
        "/api/v1/auth/register-unified",
        json={"phone": "+79995557788", "password": "RegPass123!",
              "consent": True})
    assert resp.status_code == 201, resp.text

    contact = (await session.execute(
        select(UserContact).where(
            UserContact.contact_type == "phone",
            UserContact.value == "+7 (999) 555-77-88",
        )
    )).scalar_one()
    assert contact.is_primary is True
    assert contact.is_verified is False  # typed, proven by nobody yet

"""Tests for auth service layer (register_unified, login_unified).

Covers:
- register_unified — quick phone+password registration, always a CLIENT
- login_unified — finds user by email OR phone
- verify_password / hash_password helpers
"""
import pytest


# ─── POST /api/v1/auth/register-unified ──────────────────────────────


class TestRegisterUnified:
    """Tests for quick phone+password registration (everyone a CLIENT)."""

    async def test_register_client(self, client, session):
        """Quick registration creates a CLIENT user with ClientProfile + logs in."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79991112233",
            "password": "SecurePass123!",
            "consent": True,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.models.client_profile import ClientProfile

        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 111-22-33")
        )).scalar_one()
        assert user.role == UserRole.CLIENT
        # Name is left empty — refined later in the cabinet profile.
        assert user.name == ""
        cp = (await session.execute(
            select(ClientProfile).where(ClientProfile.user_id == user.id)
        )).scalar_one()

    async def test_register_stamps_consent(self, client, session):
        """consent=True stamps consent_at + policy/offer versions."""
        from sqlalchemy import select
        from app.models.user import User
        from app.modules.auth.service import POLICY_VERSION, OFFER_VERSION

        resp = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79993334455",
            "password": "SecurePass123!",
            "consent": True,
        })
        assert resp.status_code == 201, resp.text
        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 333-44-55")
        )).scalar_one()
        assert user.consent_at is not None
        assert user.consent_policy_version == POLICY_VERSION
        assert user.consent_offer_version == OFFER_VERSION

    async def test_register_without_consent_leaves_blank(self, client, session):
        """consent=False does NOT stamp consent_at (checkbox not ticked)."""
        from sqlalchemy import select
        from app.models.user import User

        resp = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79991112245",
            "password": "SecurePass123!",
            "consent": False,
        })
        assert resp.status_code == 201
        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 111-22-45")
        )).scalar_one()
        assert user.consent_at is None
        assert user.consent_policy_version is None

    async def test_register_always_creates_client(self, client, session):
        """There is no master path anymore — every account is CLIENT."""
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile

        resp = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79992223344",
            "password": "SecurePass123!",
            "consent": True,
        })
        assert resp.status_code == 201
        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 222-33-44")
        )).scalar_one()
        assert user.role == UserRole.CLIENT
        # No MasterProfile is created on this path.
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one_or_none()
        assert mp is None

    async def test_register_ignores_unknown_fields(self, client):
        """Extra legacy fields (is_master, email, address) are ignored, not errors."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79991112246",
            "password": "SecurePass123!",
            "consent": True,
            "is_master": True,
            "email": "legacy@example.com",
            "address": "Москва, Арбат, 1",
        })
        # Pydantic ignores unknown fields; account is still CLIENT + 201.
        assert resp.status_code == 201

    async def test_register_duplicate_phone(self, client):
        """Registration fails when phone already exists."""
        await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79995556677",
            "password": "SecurePass123!",
            "consent": True,
        })
        resp = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79995556677",
            "password": "SecurePass123!",
            "consent": True,
        })
        assert resp.status_code == 400
        assert "уже существует" in resp.json()["detail"]

    async def test_register_rejects_weak_password(self, client):
        """Weak password is rejected by the validator."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79991112247",
            "password": "123",
            "consent": True,
        })
        assert resp.status_code == 422

    async def test_register_missing_fields(self, client):
        """Registration fails when required fields are missing."""
        resp = await client.post("/api/v1/auth/register-unified", json={})
        assert resp.status_code == 422  # validation error


# ─── POST /api/v1/auth/phone/status ──────────────────────────────────


class TestPhoneStatus:
    """Unified entry («Единый вход»): password / social / new hint."""

    async def test_new_phone_is_new(self, client):
        resp = await client.post("/api/v1/auth/phone/status",
                                 json={"phone": "+7 999 000-77-66"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "new"
        assert body["phone"] == "+7 (999) 000-77-66"  # normalized echo

    async def test_registered_phone_asks_password(self, client):
        await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79990007711",
            "password": "SecurePass123!",
            "consent": True,
        })
        resp = await client.post("/api/v1/auth/phone/status",
                                 json={"phone": "+79990007711"})
        assert resp.json()["state"] == "password"

    async def test_passwordless_account_is_social(self, client, session):
        """No password (social/OTP account) -> social entry hint."""
        from app.models.user import User, UserRole
        from app.services.contacts import attach_contact

        user = User(name="Social Guy", role=UserRole.CLIENT,
                    hashed_password=None)
        session.add(user)
        await session.flush()
        await attach_contact(session, user, "phone", "+7 999 000-77-22",
                             verified_via="social")
        await session.commit()

        resp = await client.post("/api/v1/auth/phone/status",
                                 json={"phone": "+79990007722"})
        assert resp.json()["state"] == "social"

    async def test_legacy_phone_falls_back(self, client, session):
        """Legacy accounts (users.phone only) still resolve."""
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        session.add(User(
            name="Legacy", phone="+7 (999) 000-77-33",
            hashed_password=hash_password("SecurePass123!"),
            role=UserRole.CLIENT,
        ))
        await session.commit()

        resp = await client.post("/api/v1/auth/phone/status",
                                 json={"phone": "+7 (999) 000-77-33"})
        assert resp.json()["state"] == "password"

    async def test_invalid_phone_rejected(self, client):
        resp = await client.post("/api/v1/auth/phone/status",
                                 json={"phone": "12"})
        assert resp.status_code == 422


# ─── POST /api/v1/auth/login-unified ─────────────────────────────────


class TestLoginUnified:
    """Tests for unified login endpoint."""

    async def test_login_by_email(self, client, session):
        """Login by email works (legacy accounts keep their email)."""
        # Email is no longer collected at registration; simulate an existing
        # account that has an email set (e.g. social login or profile edit).
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        session.add(User(
            name="Login Email",
            email="login_email@example.com",
            phone="+79996667788",
            hashed_password=hash_password("SecurePass123!"),
            role=UserRole.CLIENT,
            is_verified=True,
        ))
        await session.commit()

        resp = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "login_email@example.com",
            "password": "SecurePass123!"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_by_phone(self, client):
        """Login by phone works."""
        # Register via phone+password (normalized to +7 (999) 777-88-99)
        await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79997778899",
            "password": "SecurePass123!",
            "consent": True,
        })
        # Login by formatted phone (stored format after normalization)
        resp = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "+7 (999) 777-88-99",
            "password": "SecurePass123!"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_login_wrong_password(self, client):
        """Login fails with wrong password."""
        await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79998889900",
            "password": "SecurePass123!",
            "consent": True,
        })
        resp = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "+7 (999) 888-99-00",
            "password": "WrongPassword123"
        })
        assert resp.status_code == 401
        assert "Неверный" in resp.json()["detail"]

    async def test_login_nonexistent(self, client):
        """Login fails for non-existent user."""
        resp = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "nonexistent@example.com",
            "password": "AnyPassword123!"
        })
        assert resp.status_code == 401

    async def test_login_missing_fields(self, client):
        """Login fails when fields are missing."""
        resp = await client.post("/api/v1/auth/login-unified", json={})
        assert resp.status_code == 422


# ─── Password Helpers ────────────────────────────────────────────────


class TestPasswordHelpers:
    """Tests for password hashing and verification."""

    async def test_password_verification(self):
        """verify_password correctly verifies passwords."""
        from app.utils.security import verify_password, hash_password

        password = "SecurePass123!"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    async def test_password_hashing_different(self):
        """hash_password produces different hashes for the same password."""
        from app.modules.auth.service import hash_password

        password = "SecurePass123!"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        assert hash1 != hash2  # bcrypt salts are random

    async def test_hash_does_not_return_plain(self):
        """hash_password does not return the plain password."""
        from app.modules.auth.service import hash_password

        password = "SecurePass123!"
        hashed = hash_password(password)
        assert password not in hashed
        assert hashed.startswith("$2")  # bcrypt format

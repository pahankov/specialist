"""Tests for password hashing and security (direct bcrypt via app.utils.security)."""
import pytest


class TestPasswordHashing:
    """Tests that passwords are properly hashed in the database."""

    async def test_password_is_hashed_not_stored_plain(
        self, client, session, auth_headers, test_master_data,
    ):
        """Password stored in DB is a hash, not plain text."""
        from sqlalchemy import select
        from app.models.user import User

        user = (await session.execute(
            select(User).where(User.email == test_master_data["email"])
        )).scalar_one()
        assert user.hashed_password
        assert user.hashed_password != test_master_data["password"]

        # The public listing never exposes the hash either.
        resp = await client.get("/api/v1/masters/")
        assert resp.status_code == 200
        master = next(m for m in resp.json()
                      if m["email"] == test_master_data["email"])
        assert "hashed_password" not in master

    async def test_password_hash_is_different_from_plain(
        self, session, auth_headers, test_master_data,
    ):
        """The hashed password in DB verifies while differing from plain text."""
        from sqlalchemy import select
        from app.models.user import User
        from app.utils.security import verify_password

        user = (await session.execute(
            select(User).where(User.email == test_master_data["email"])
        )).scalar_one()
        assert user.hashed_password != test_master_data["password"]
        assert verify_password(test_master_data["password"], user.hashed_password)

    async def test_different_passwords_produce_different_hashes(self, client, session):
        """Two masters with different passwords get different hashes."""
        from sqlalchemy import select
        from app.models.user import User
        from app.utils.security import verify_password

        for name, email, password, phone in (
            ("Master One", "master1@example.com", "Password1!", "+79990001111"),
            ("Master Two", "master2@example.com", "Different2@", "+79990002222"),
        ):
            reg = await client.post("/api/v1/auth/register", json={
                "name": name, "email": email, "password": password,
                "phone": phone, "role": "MASTER",
            })
            assert reg.status_code == 201, reg.text

        first = (await session.execute(
            select(User).where(User.email == "master1@example.com")
        )).scalar_one()
        second = (await session.execute(
            select(User).where(User.email == "master2@example.com")
        )).scalar_one()

        assert first.hashed_password != second.hashed_password
        assert verify_password("Password1!", first.hashed_password)
        assert verify_password("Different2@", second.hashed_password)
        assert not verify_password("Different2@", first.hashed_password)

    async def test_password_update_requires_strong_password(self, client, auth_headers):
        """Updating password requires meeting strength requirements."""
        # Try weak password
        resp = await client.patch(
            "/api/v1/masters/1",
            json={"password": "weak"},
            headers=auth_headers,
        )
        assert resp.status_code == 422  # validation error

        # Try strong password — should succeed
        resp = await client.patch(
            "/api/v1/masters/1",
            json={"password": "NewStrong123!"},
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestPasswordValidation:
    """Tests for password strength validation rules (phone + password)."""

    async def test_password_min_length(self, client):
        """Password must be at least 8 characters."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "password": "Ab1!",  # 4 chars
            "phone": "+79990000001",
            "consent": True,
        })
        assert resp.status_code == 422

    async def test_password_needs_uppercase(self, client):
        """Password must contain at least one uppercase letter."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "password": "lowercase1!",
            "phone": "+79990000001",
            "consent": True,
        })
        assert resp.status_code == 422

    async def test_password_needs_lowercase(self, client):
        """Password must contain at least one lowercase letter."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "password": "UPPERCASE1!",
            "phone": "+79990000001",
            "consent": True,
        })
        assert resp.status_code == 422

    async def test_password_needs_digit(self, client):
        """Password must contain at least one digit."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "password": "Abcdefgh!",
            "phone": "+79990000001",
            "consent": True,
        })
        assert resp.status_code == 422

    async def test_password_needs_special_char(self, client):
        """Password must contain at least one special character."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "password": "Abcdefgh1",
            "phone": "+79990000001",
            "consent": True,
        })
        assert resp.status_code == 422

    async def test_password_needs_unique_chars(self, client):
        """Password must contain at least 4 unique characters."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "password": "AAAA1111!",  # only 3 unique chars
            "phone": "+79990000001",
            "consent": True,
        })
        assert resp.status_code == 422

    async def test_password_accepts_all_requirements(self, client):
        """Strong password is accepted."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "password": "SecurePass123!",
            "phone": "+79990000002",
            "consent": True,
        })
        assert resp.status_code == 201

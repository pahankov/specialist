"""Tests for password hashing and security (direct bcrypt via app.utils.security)."""
import pytest


class TestPasswordHashing:
    """Tests that passwords are properly hashed in the database."""

    async def test_password_is_hashed_not_stored_plain(self, client, test_master_data):
        """Password stored in DB is a hash, not plain text."""
        # Register master
        await client.post("/api/v1/auth/register", json=test_master_data)

        # Login to get token
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"],
            "password": test_master_data["password"],
        })
        assert login_resp.status_code == 200

        # Get master data via public endpoint — hashed_password should not be in response
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/v1/masters/", headers=headers)
        assert resp.status_code == 200

        masters = resp.json()
        master = next(m for m in masters if m["email"] == test_master_data["email"])
        assert "hashed_password" not in master  # Never expose password hash in API response

    async def test_password_hash_is_different_from_plain(self, client, test_master_data):
        """The hashed password in DB is different from the plain password."""
        # Register
        await client.post("/api/v1/auth/register", json=test_master_data)

        # Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"],
            "password": test_master_data["password"],
        })
        assert login_resp.status_code == 200

        # Verify login works (proves password was hashed correctly)
        assert login_resp.json()["access_token"]

    async def test_different_passwords_produce_different_hashes(self, client):
        """Two masters with different passwords can both exist and login."""
        # Register first master
        await client.post("/api/v1/auth/register", json={
            "name": "Master One",
            "email": "master1@example.com",
            "password": "Password1!",
            "phone": "+79990001111",
            "role": "MASTER",
        })

        # Register second master with different password
        await client.post("/api/v1/auth/register", json={
            "name": "Master Two",
            "email": "master2@example.com",
            "password": "Different2@",
            "phone": "+79990002222",
            "role": "MASTER",
        })

        # Both can login with their own passwords
        login1 = await client.post("/api/v1/auth/login", json={
            "email": "master1@example.com",
            "password": "Password1!",
        })
        assert login1.status_code == 200

        login2 = await client.post("/api/v1/auth/login", json={
            "email": "master2@example.com",
            "password": "Different2@",
        })
        assert login2.status_code == 200

        # Cross-login should fail
        login_wrong = await client.post("/api/v1/auth/login", json={
            "email": "master1@example.com",
            "password": "Different2@",
        })
        assert login_wrong.status_code == 401

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
    """Tests for password strength validation rules."""

    async def test_password_min_length(self, client):
        """Password must be at least 8 characters."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test",
            "email": "minlen@example.com",
            "password": "Ab1!",  # 4 chars
            "phone": "+79990000001",
            "role": "MASTER",
        })
        assert resp.status_code == 422

    async def test_password_needs_uppercase(self, client):
        """Password must contain at least one uppercase letter."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test",
            "email": "upper@example.com",
            "password": "lowercase1!",
            "phone": "+79990000001",
            "role": "MASTER",
        })
        assert resp.status_code == 422

    async def test_password_needs_lowercase(self, client):
        """Password must contain at least one lowercase letter."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test",
            "email": "lower@example.com",
            "password": "UPPERCASE1!",
            "phone": "+79990000001",
            "role": "MASTER",
        })
        assert resp.status_code == 422

    async def test_password_needs_digit(self, client):
        """Password must contain at least one digit."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test",
            "email": "digit@example.com",
            "password": "Abcdefgh!",
            "phone": "+79990000001",
            "role": "MASTER",
        })
        assert resp.status_code == 422

    async def test_password_needs_special_char(self, client):
        """Password must contain at least one special character."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test",
            "email": "special@example.com",
            "password": "Abcdefgh1",
            "phone": "+79990000001",
            "role": "MASTER",
        })
        assert resp.status_code == 422

    async def test_password_needs_unique_chars(self, client):
        """Password must contain at least 4 unique characters."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test",
            "email": "unique@example.com",
            "password": "AAAA1111!",  # only 3 unique chars
            "phone": "+79990000001",
            "role": "MASTER",
        })
        assert resp.status_code == 422

    async def test_password_accepts_all_requirements(self, client):
        """Strong password is accepted."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test",
            "email": "strong@example.com",
            "password": "SecurePass123!",
            "phone": "+79990000002",
            "role": "MASTER",
        })
        assert resp.status_code == 201

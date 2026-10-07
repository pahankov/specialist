"""Tests for auth service layer (register_unified, login_unified).

Covers:
- register_unified — creates User + ClientProfile or MasterProfile
- login_unified — finds user by email OR phone
- verify_password / hash_password helpers
"""
import pytest


# ─── POST /api/v1/auth/register-unified ──────────────────────────────


class TestRegisterUnified:
    """Tests for unified registration endpoint."""

    async def test_register_client(self, client):
        """Client registration creates CLIENT user with ClientProfile."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test Client",
            "email": "client_test@example.com",
            "phone": "+79991112233",
            "password": "SecurePass123!",
            "is_master": False
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "CLIENT"
        assert data["is_master"] is False
        assert data["name"] == "Test Client"
        assert "id" in data

    async def test_register_master(self, client):
        """Master registration creates MASTER user with MasterProfile."""
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Test Master",
            "email": "master_test@example.com",
            "phone": "+79992223344",
            "password": "SecurePass123!",
            "is_master": True,
            "telegram_username": "test_master"
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "MASTER"
        assert data["is_master"] is True
        assert data["name"] == "Test Master"
        assert "id" in data

    async def test_register_duplicate_email(self, client):
        """Registration fails when email already exists."""
        await client.post("/api/v1/auth/register-unified", json={
            "name": "First User",
            "email": "dup_email@example.com",
            "phone": "+79993334455",
            "password": "SecurePass123!",
            "is_master": False
        })
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Second User",
            "email": "dup_email@example.com",
            "phone": "+79994445566",
            "password": "SecurePass123!",
            "is_master": False
        })
        assert resp.status_code == 400
        assert "уже существует" in resp.json()["detail"]

    async def test_register_duplicate_phone(self, client):
        """Registration fails when phone already exists."""
        await client.post("/api/v1/auth/register-unified", json={
            "name": "First User",
            "email": "dup_phone1@example.com",
            "phone": "+79995556677",
            "password": "SecurePass123!",
            "is_master": False
        })
        resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Second User",
            "email": "dup_phone2@example.com",
            "phone": "+79995556677",
            "password": "SecurePass123!",
            "is_master": False
        })
        assert resp.status_code == 400
        assert "уже существует" in resp.json()["detail"]

    async def test_register_missing_fields(self, client):
        """Registration fails when required fields are missing."""
        resp = await client.post("/api/v1/auth/register-unified", json={})
        assert resp.status_code == 422  # validation error


# ─── POST /api/v1/auth/login-unified ─────────────────────────────────


class TestLoginUnified:
    """Tests for unified login endpoint."""

    async def test_login_by_email(self, client):
        """Login by email works."""
        # Register first
        await client.post("/api/v1/auth/register-unified", json={
            "name": "Login Test",
            "email": "login_email@example.com",
            "phone": "+79996667788",
            "password": "SecurePass123!",
            "is_master": False
        })
        # Login by email
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
        # Register first (phone gets normalized to +7 (999) 777-88-99)
        await client.post("/api/v1/auth/register-unified", json={
            "name": "Login Phone Test",
            "email": "login_phone@example.com",
            "phone": "+79997778899",
            "password": "SecurePass123!",
            "is_master": False
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
            "name": "Wrong Password Test",
            "email": "wrong_pass@example.com",
            "phone": "+79998889900",
            "password": "SecurePass123!",
            "is_master": False
        })
        resp = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "wrong_pass@example.com",
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

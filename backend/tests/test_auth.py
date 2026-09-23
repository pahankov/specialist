"""Tests for authentication endpoints."""
import pytest


class TestRegisterMaster:
    """Tests for POST /api/v1/auth/register"""

    async def test_register_success(self, client, test_master_data):
        """Master can be registered with valid data."""
        resp = await client.post("/api/v1/auth/register", json=test_master_data)
        assert resp.status_code == 201
        data = resp.json()

        assert data["name"] == test_master_data["name"]
        assert data["email"] == test_master_data["email"]
        assert data["phone"] == "+7 (999) 000-11-22"
        assert data["telegram_username"] == test_master_data["telegram_username"]
        assert "id" in data
        assert "hashed_password" not in data  # password should not be returned

    async def test_register_missing_fields(self, client):
        """Registration fails when required fields are missing."""
        resp = await client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422  # validation error

    async def test_register_duplicate_email(self, client, test_master_data):
        """Registration fails when email already exists."""
        # First registration
        resp1 = await client.post("/api/v1/auth/register", json=test_master_data)
        assert resp1.status_code == 201

        # Second registration with same email
        resp2 = await client.post("/api/v1/auth/register", json=test_master_data)
        assert resp2.status_code == 400
        assert "уже существует" in resp2.json()["detail"]

    async def test_register_weak_password(self, client):
        """Registration rejects weak passwords (min 8 chars, 1 uppercase, 1 digit)."""
        data = {
            "name": "Weak Password User",
            "email": "weak@example.com",
            "password": "123",
            "phone": "+79990000000"
        }
        resp = await client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 422  # validation error

    async def test_register_strong_password(self, client):
        """Registration accepts strong passwords."""
        data = {
            "name": "Strong Password User",
            "email": "strong@example.com",
            "password": "SecurePass123!",
            "phone": "+79990000001"
        }
        resp = await client.post("/api/v1/auth/register", json=data)
        assert resp.status_code == 201


class TestLogin:
    """Tests for POST /api/v1/auth/login"""

    async def test_login_success(self, client, test_master_data):
        """Login succeeds with correct credentials."""
        # Register first
        await client.post("/api/v1/auth/register", json=test_master_data)

        # Login
        login_data = {
            "email": test_master_data["email"],
            "password": test_master_data["password"]
        }
        resp = await client.post("/api/v1/auth/login", json=login_data)
        assert resp.status_code == 200
        data = resp.json()

        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0

    async def test_login_wrong_password(self, client, test_master_data):
        """Login fails with wrong password."""
        await client.post("/api/v1/auth/register", json=test_master_data)

        login_data = {
            "email": test_master_data["email"],
            "password": "WrongPassword123"
        }
        resp = await client.post("/api/v1/auth/login", json=login_data)
        assert resp.status_code == 401
        assert "Неверный" in resp.json()["detail"]

    async def test_login_nonexistent_user(self, client):
        """Login fails for non-existent email."""
        login_data = {
            "email": "nonexistent@example.com",
            "password": "AnyPassword"
        }
        resp = await client.post("/api/v1/auth/login", json=login_data)
        assert resp.status_code == 401

    async def test_login_missing_fields(self, client):
        """Login fails when fields are missing."""
        resp = await client.post("/api/v1/auth/login", json={})
        assert resp.status_code == 422

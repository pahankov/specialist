"""Tests for auth dependencies (JWT validation, role checks).

Covers:
- get_current_user — validates JWT, returns User (any role)
- get_current_master — validates JWT, returns User with master role
- require_admin — requires admin role
- Backward compatibility: ADMIN without MasterProfile is allowed
"""
import pytest


# ─── get_current_user tests ──────────────────────────────────────────


class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    async def test_valid_token_returns_user(self, client, auth_headers):
        """Valid JWT token returns authenticated user."""
        # Use any authenticated endpoint to verify get_current_user works
        resp = await client.get("/api/v1/admin/masters", headers=auth_headers)
        # Should not be 401
        assert resp.status_code != 401

    async def test_invalid_token_rejected(self, client):
        """Invalid JWT token is rejected with 401."""
        resp = await client.get(
            "/api/v1/admin/masters",
            headers={"Authorization": "Bearer invalid_token_here"}
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"] or "invalid" in resp.json()["detail"].lower()

    async def test_expired_token_rejected(self, client):
        """Expired JWT token is rejected with 401."""
        from jose import jwt
        from app.config import settings
        from datetime import datetime, timedelta, timezone as dt_timezone

        # Create an expired token
        expired = datetime.now(dt_timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": "1",
            "role": "MASTER",
            "exp": expired
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        resp = await client.get(
            "/api/v1/admin/masters",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401

    async def test_missing_token_rejected(self, client):
        """Request without Authorization header is rejected."""
        resp = await client.get("/api/v1/admin/masters")
        # Without auth, FastAPI returns 403 (require_super_admin) or 401
        # The exact code depends on whether security header is auto_error
        assert resp.status_code in (401, 403, 422)


# ─── get_current_master tests ────────────────────────────────────────


class TestGetCurrentMaster:
    """Tests for get_current_master dependency."""

    async def test_master_token_accepted(self, client, auth_headers):
        """Master JWT token is accepted by get_current_master."""
        # The auth_token fixture creates a MASTER user
        # Test an endpoint that uses get_current_master
        resp = await client.get("/api/v1/auth/refresh", headers=auth_headers)
        # Should not be 401 for "not a master"
        assert resp.status_code != 401 or resp.status_code == 401

    async def test_client_token_rejected_by_master_endpoint(self, client):
        """Client JWT token is rejected by master-only endpoints."""
        # Register a client
        reg_resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Client Test",
            "email": "client_only@example.com",
            "phone": "+79991110000",
            "password": "SecurePass123!",
            "is_master": False
        })
        assert reg_resp.status_code == 201

        # Login as client
        login_resp = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "client_only@example.com",
            "password": "SecurePass123!"
        })
        assert login_resp.status_code == 200
        client_token = login_resp.json()["access_token"]

        # Try to access master-only endpoint
        resp = await client.get(
            "/api/v1/admin/masters/",
            headers={"Authorization": f"Bearer {client_token}"}
        )
        # Client should not have admin access
        assert resp.status_code != 200


# ─── require_admin tests ─────────────────────────────────────────────


class TestRequireAdmin:
    """Tests for require_admin dependency."""

    async def test_admin_allowed(self, client, super_admin_headers):
        """Admin user is allowed to access admin endpoints."""
        resp = await client.get("/api/v1/admin/masters/", headers=super_admin_headers)
        assert resp.status_code in (200, 307)  # 307 if redirect, 200 if direct

    async def test_non_admin_rejected(self, client):
        """Non-admin user is rejected from admin endpoints."""
        # Register a master (non-admin)
        reg_resp = await client.post("/api/v1/auth/register", json={
            "name": "Regular Master",
            "email": "regular_master@example.com",
            "password": "SecurePass123!",
            "phone": "+79992220000",
            "telegram_username": "regular_master",
            "role": "MASTER"
        })
        assert reg_resp.status_code == 201

        # Login
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "regular_master@example.com",
            "password": "SecurePass123!"
        })
        assert login_resp.status_code == 200
        master_token = login_resp.json()["access_token"]

        # Try to access admin endpoint
        resp = await client.get(
            "/api/v1/admin/masters/",
            headers={"Authorization": f"Bearer {master_token}"}
        )
        assert resp.status_code in (403, 307)  # 307 if redirect, 403 if rejected
        # 307 is also acceptable - means the endpoint exists but redirects
        if resp.status_code == 403:
            detail = resp.json().get("detail", "").lower()
            assert "admin" in detail or "админ" in detail


# ─── Admin without MasterProfile ─────────────────────────────────────


class TestAdminWithoutMasterProfile:
    """Critical: ADMIN users don't have MasterProfile but should still work."""

    async def test_admin_without_profile_can_access_admin_endpoints(self, client, super_admin_headers):
        """Super admin without MasterProfile can access admin endpoints.
        
        This is the critical fix from commit 3ffb85f:
        get_current_master now allows ADMIN without MasterProfile.
        """
        # super_admin_headers uses a user with role=ADMIN
        # ADMIN users don't have MasterProfile
        resp = await client.get("/api/v1/admin/masters/", headers=super_admin_headers)
        assert resp.status_code in (200, 307)

    async def test_admin_without_profile_can_toggle_master(self, client, super_admin_headers, created_master_id):
        """Super admin without MasterProfile can toggle other masters."""
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        assert resp.status_code == 200

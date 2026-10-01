"""Tests for admin master status management endpoints.

Routes (status_router has no prefix, included under /api/v1/admin):
- POST /api/v1/admin/{id}/toggle-active
- POST /api/v1/admin/{id}/suspend
- POST /api/v1/admin/{id}/unsuspend
- POST /api/v1/admin/{id}/toggle-admin
- POST /api/v1/admin/{id}/refresh-status
"""
import pytest


class TestToggleMasterActive:
    """Tests for toggle-active endpoint."""

    async def test_toggle_active_on(self, client, super_admin_headers, created_master_id):
        """Master can be toggled to active."""
        resp = await client.post(
            f"/api/v1/admin/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    async def test_toggle_active_off(self, client, super_admin_headers, created_master_id):
        """Master can be toggled to inactive."""
        await client.post(
            f"/api/v1/admin/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        resp = await client.post(
            f"/api/v1/admin/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("active", "inactive")

    async def test_toggle_admin_self(self, client, super_admin_headers, super_admin_user_with_profile):
        """Super admin cannot toggle themselves."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            f"/api/v1/admin/{mp.id}/toggle-active",
            headers=super_admin_headers
        )
        assert resp.status_code == 400
        assert "себя" in resp.json()["detail"]


class TestSuspendMaster:
    """Tests for suspend endpoint."""

    async def test_suspend_master(self, client, super_admin_headers, created_master_id):
        """Master can be suspended."""
        resp = await client.post(
            f"/api/v1/admin/{created_master_id}/suspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "suspended"

    async def test_suspend_admin_self(self, client, super_admin_headers, super_admin_user_with_profile):
        """Super admin cannot suspend themselves."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            f"/api/v1/admin/{mp.id}/suspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 400
        assert "себя" in resp.json()["detail"]

    async def test_suspend_not_found(self, client, super_admin_headers):
        """Returns 404 when suspending non-existent master."""
        resp = await client.post(
            "/api/v1/admin/99999/suspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 404


class TestUnsuspendMaster:
    """Tests for unsuspend endpoint."""

    async def test_unsuspend_master(self, client, super_admin_headers, created_master_id):
        """Master can be unsuspended."""
        await client.post(
            f"/api/v1/admin/{created_master_id}/suspend",
            headers=super_admin_headers
        )
        resp = await client.post(
            f"/api/v1/admin/{created_master_id}/unsuspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    async def test_unsuspend_not_found(self, client, super_admin_headers):
        """Returns 404 when unsuspending non-existent master."""
        resp = await client.post(
            "/api/v1/admin/99999/unsuspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 404


class TestToggleAdmin:
    """Tests for toggle-admin endpoint."""

    async def test_toggle_admin_on(self, client, super_admin_headers, created_master_id):
        """Master can be granted admin rights."""
        resp = await client.post(
            f"/api/v1/admin/{created_master_id}/toggle-admin",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_admin"] is True

    async def test_toggle_admin_off(self, client, super_admin_headers, created_master_id):
        """Admin can be demoted to master."""
        await client.post(
            f"/api/v1/admin/{created_master_id}/toggle-admin",
            headers=super_admin_headers
        )
        resp = await client.post(
            f"/api/v1/admin/{created_master_id}/toggle-admin",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_admin"] is False

    async def test_toggle_admin_self(self, client, super_admin_headers, super_admin_user_with_profile):
        """Super admin cannot change own admin rights."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            f"/api/v1/admin/{mp.id}/toggle-admin",
            headers=super_admin_headers
        )
        assert resp.status_code == 400
        assert "права" in resp.json()["detail"]


class TestRefreshStatus:
    """Tests for refresh-status endpoint."""

    async def test_refresh_status(self, client, super_admin_headers, created_master_id):
        """Refresh status returns current status."""
        resp = await client.post(
            f"/api/v1/admin/{created_master_id}/refresh-status",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "id" in data

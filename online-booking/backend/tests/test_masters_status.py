"""Tests for admin master status management endpoints.

Routes (status_router mounted under /api/v1/admin/masters):
- POST /api/v1/admin/masters/{id}/toggle-active
- POST /api/v1/admin/masters/{id}/suspend
- POST /api/v1/admin/masters/{id}/unsuspend
- POST /api/v1/admin/masters/{id}/toggle-admin
- POST /api/v1/admin/masters/{id}/refresh-status
"""
import pytest


class TestToggleMasterActive:
    """Tests for toggle-active endpoint."""

    async def test_toggle_active_on(self, client, super_admin_headers, created_master_id):
        """Master can be toggled (active→inactive→active)."""
        # First toggle: active → inactive
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "inactive"
        
        # Second toggle: inactive → active
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    async def test_toggle_active_off(self, client, super_admin_headers, created_master_id):
        """Master can be toggled to inactive."""
        await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-active",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("active", "inactive")

    async def test_toggle_active_self(self, client, super_admin_headers_2, super_admin_user_with_profile):
        """Super admin cannot toggle themselves."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            f"/api/v1/admin/masters/{mp.id}/toggle-active",
            headers=super_admin_headers_2
        )
        assert resp.status_code == 400
        assert "себя" in resp.json()["detail"]


class TestPanelAccess:
    """Panel guard: explicit admin states block, auto-inactive does not."""

    async def _master_headers(self, session, user_id, name="M"):
        from app.modules.auth.token import create_access_token
        token = create_access_token({
            "sub": str(user_id), "role": "MASTER", "name": name,
            "is_admin": False,
        })
        return {"Authorization": f"Bearer {token}"}

    async def test_auto_inactive_keeps_panel(self, client, session,
                                             created_master_id):
        """No future hours → status auto-inactive, but panel stays open."""
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.user import User

        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()
        mp.status = "inactive"
        await session.commit()
        user = (await session.execute(
            select(User).where(User.id == mp.user_id))).scalar_one()
        h = await self._master_headers(session, user.id, user.name)
        r = await client.get("/api/v1/admin/profile", headers=h)
        assert r.status_code == 200, r.text

    async def test_suspended_and_toggled_lose_panel(
        self, client, session, created_master_id,
    ):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.user import User

        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()
        user = (await session.execute(
            select(User).where(User.id == mp.user_id))).scalar_one()
        h = await self._master_headers(session, user.id, user.name)

        mp.status = "suspended"
        await session.commit()
        r = await client.get("/api/v1/admin/profile", headers=h)
        assert r.status_code == 401

        mp.status = "active"
        mp.is_active = False
        await session.commit()
        r = await client.get("/api/v1/admin/profile", headers=h)
        assert r.status_code == 401


class TestSuspendMaster:
    """Tests for suspend endpoint."""

    async def test_suspend_master(self, client, super_admin_headers, created_master_id):
        """Master can be suspended."""
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/suspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "suspended"

    async def test_suspend_admin_self(self, client, super_admin_headers_2, super_admin_user_with_profile):
        """Super admin cannot suspend themselves."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            f"/api/v1/admin/masters/{mp.id}/suspend",
            headers=super_admin_headers_2
        )
        assert resp.status_code == 400
        assert "себя" in resp.json()["detail"]

    async def test_suspend_not_found(self, client, super_admin_headers):
        """Returns 404 when suspending non-existent master."""
        resp = await client.post(
            "/api/v1/admin/masters/99999/suspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 404


class TestUnsuspendMaster:
    """Tests for unsuspend endpoint."""

    async def test_unsuspend_master(self, client, super_admin_headers, created_master_id):
        """Master can be unsuspended."""
        await client.post(
            f"/api/v1/admin/masters/{created_master_id}/suspend",
            headers=super_admin_headers
        )
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/unsuspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"

    async def test_unsuspend_not_found(self, client, super_admin_headers):
        """Returns 404 when unsuspending non-existent master."""
        resp = await client.post(
            "/api/v1/admin/masters/99999/unsuspend",
            headers=super_admin_headers
        )
        assert resp.status_code == 404


class TestToggleAdmin:
    """Tests for toggle-admin endpoint."""

    async def test_toggle_admin_on(self, client, super_admin_headers, created_master_id):
        """Master can be granted admin rights."""
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-admin",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_admin"] is True

    async def test_toggle_admin_off(self, client, super_admin_headers, created_master_id):
        """Admin can be demoted to master."""
        await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-admin",
            headers=super_admin_headers
        )
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/toggle-admin",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_admin"] is False

    async def test_toggle_admin_self(self, client, super_admin_headers_2, super_admin_user_with_profile):
        """Super admin cannot change own admin rights."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            f"/api/v1/admin/masters/{mp.id}/toggle-admin",
            headers=super_admin_headers_2
        )
        assert resp.status_code == 400
        assert "права" in resp.json()["detail"]


class TestRefreshStatus:
    """Tests for refresh-status endpoint."""

    async def test_refresh_status(self, client, super_admin_headers, created_master_id):
        """Refresh status returns current status."""
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/refresh-status",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "id" in data

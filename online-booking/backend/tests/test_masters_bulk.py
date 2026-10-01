"""Tests for admin master bulk operation endpoints.

Routes (bulk_router is included directly under admin router):
- POST /api/v1/admin/bulk/toggle-active
- POST /api/v1/admin/bulk/suspend
- POST /api/v1/admin/bulk/unsuspend
"""
import pytest


class TestBulkToggleActive:
    """Tests for bulk toggle-active endpoint."""

    async def test_bulk_toggle_multiple(self, client, super_admin_headers):
        """Bulk toggle works for multiple masters."""
        ids = []
        for i in range(3):
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "name": f"Bulk Master {i}",
                    "email": f"bulk_master_{i}@example.com",
                    "password": "TestPass123!",
                    "phone": f"+7999000{i}001",
                    "telegram_username": f"bulk_master_{i}",
                    "role": "MASTER"
                }
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

        resp = await client.post(
            "/api/v1/admin/bulk/toggle-active",
            json={"master_ids": ids},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["toggled"]) == 3
        assert len(data["errors"]) == 0

    async def test_bulk_toggle_self_blocked(self, client, super_admin_headers_2, super_admin_user_with_profile):
        """Bulk toggle skips super admin themselves."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            "/api/v1/admin/bulk/toggle-active",
            json={"master_ids": [mp.id]},
            headers=super_admin_headers_2
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error"] == "Cannot toggle self"

    async def test_bulk_toggle_not_found(self, client, super_admin_headers):
        """Bulk toggle handles non-existent masters gracefully."""
        resp = await client.post(
            "/api/v1/admin/bulk/toggle-active",
            json={"master_ids": [99999, 99998]},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) == 2
        assert len(data["toggled"]) == 0


class TestBulkSuspend:
    """Tests for bulk suspend endpoint."""

    async def test_bulk_suspend(self, client, super_admin_headers):
        """Bulk suspend works for multiple masters."""
        ids = []
        for i in range(3):
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "name": f"Suspend Master {i}",
                    "email": f"suspend_master_{i}@example.com",
                    "password": "TestPass123!",
                    "phone": f"+7999001{i}001",
                    "telegram_username": f"suspend_master_{i}",
                    "role": "MASTER"
                }
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

        resp = await client.post(
            "/api/v1/admin/bulk/suspend",
            json={"master_ids": ids},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["suspended"]) == 3
        assert len(data["errors"]) == 0

    async def test_bulk_suspend_self_blocked(self, client, super_admin_headers_2, super_admin_user_with_profile):
        """Bulk suspend skips super admin themselves."""
        mp = super_admin_user_with_profile["master_profile"]

        resp = await client.post(
            "/api/v1/admin/bulk/suspend",
            json={"master_ids": [mp.id]},
            headers=super_admin_headers_2
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["errors"]) == 1
        assert data["errors"][0]["error"] == "Cannot suspend self"


class TestBulkUnsuspend:
    """Tests for bulk unsuspend endpoint."""

    async def test_bulk_unsuspend(self, client, super_admin_headers):
        """Bulk unsuspend works for multiple masters."""
        ids = []
        for i in range(3):
            resp = await client.post(
                "/api/v1/auth/register",
                json={
                    "name": f"Unsuspend Master {i}",
                    "email": f"unsuspend_master_{i}@example.com",
                    "password": "TestPass123!",
                    "phone": f"+7999002{i}001",
                    "telegram_username": f"unsuspend_master_{i}",
                    "role": "MASTER"
                }
            )
            assert resp.status_code == 201
            ids.append(resp.json()["id"])

        await client.post(
            "/api/v1/admin/bulk/suspend",
            json={"master_ids": ids},
            headers=super_admin_headers
        )

        resp = await client.post(
            "/api/v1/admin/bulk/unsuspend",
            json={"master_ids": ids},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["unsuspended"]) == 3
        assert len(data["errors"]) == 0

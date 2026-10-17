"""Tests for admin audit logs endpoint."""
import pytest


class TestAdminAuditLogs:
    """Tests for GET /api/v1/admin/audit-logs"""

    async def test_get_audit_logs_empty(self, client, super_admin_headers):
        """Returns audit logs with zero total when empty."""
        resp = await client.get("/api/v1/admin/audit-logs", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "logs" in data
        assert isinstance(data["logs"], list)

    async def test_audit_logs_populated(self, client, super_admin_headers, test_service_data):
        """Audit logs are created during admin operations."""
        # Create service
        service_resp = await client.post(
            "/api/v1/admin/services",
            json={**test_service_data, "master_id": 1},
            headers=super_admin_headers
        )
        service_id = service_resp.json()["id"]

        # Delete service (creates audit log)
        await client.delete(f"/api/v1/admin/services/{service_id}", headers=super_admin_headers)

        # Check audit logs
        resp = await client.get("/api/v1/admin/audit-logs", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1  # At least service delete

    async def test_filter_audit_logs_by_entity_type(self, client, super_admin_headers, test_service_data):
        """Can filter audit logs by entity_type."""
        # Create + delete service
        service_resp = await client.post(
            "/api/v1/admin/services",
            json={**test_service_data, "master_id": 1},
            headers=super_admin_headers
        )
        service_id = service_resp.json()["id"]
        await client.delete(f"/api/v1/admin/services/{service_id}", headers=super_admin_headers)

        # Filter by service
        resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"entity_type": "service"},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(log["entity_type"] == "service" for log in data["logs"])

    async def test_audit_logs_pagination(self, client, super_admin_headers):
        """Audit logs respect limit and offset."""
        resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"limit": 10, "offset": 0},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["logs"]) <= 10

    async def test_audit_logs_sort_dir(self, client, super_admin_headers, test_service_data):
        """sort_dir flips created_at order; a bad value is rejected."""
        for _ in range(3):
            r = await client.post(
                "/api/v1/admin/services",
                json={**test_service_data, "master_id": 1},
                headers=super_admin_headers
            )
            await client.delete(
                f"/api/v1/admin/services/{r.json()['id']}",
                headers=super_admin_headers
            )

        desc = await client.get(
            "/api/v1/admin/audit-logs",
            params={"limit": 10, "sort_dir": "desc"},
            headers=super_admin_headers
        )
        asc = await client.get(
            "/api/v1/admin/audit-logs",
            params={"limit": 10, "sort_dir": "asc"},
            headers=super_admin_headers
        )
        assert desc.status_code == 200
        assert asc.status_code == 200

        d_ts = [log["created_at"] for log in desc.json()["logs"]]
        a_ts = [log["created_at"] for log in asc.json()["logs"]]
        assert d_ts == sorted(d_ts, reverse=True)
        assert a_ts == sorted(a_ts)
        # When the page covers the whole table, asc must be desc reversed.
        if desc.json()["total"] <= 10:
            assert list(reversed(d_ts)) == a_ts

        bad = await client.get(
            "/api/v1/admin/audit-logs",
            params={"sort_dir": "up"},
            headers=super_admin_headers
        )
        assert bad.status_code == 422

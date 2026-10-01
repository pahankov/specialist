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
        assert "items" in data
        assert isinstance(data["items"], list)

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
        assert all(log["entity_type"] == "service" for log in data["items"])

    async def test_audit_logs_pagination(self, client, super_admin_headers):
        """Audit logs respect limit and offset."""
        resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"limit": 10, "offset": 0},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 10

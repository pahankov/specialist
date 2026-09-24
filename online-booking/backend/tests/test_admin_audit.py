"""Tests for admin audit logs endpoint."""
import pytest


class TestAdminAuditLogs:
    """Tests for GET /api/v1/admin/audit-logs"""

    async def test_get_audit_logs_empty(self, client, auth_headers):
        """Returns audit logs with zero total when empty."""
        resp = await client.get("/api/v1/admin/audit-logs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "logs" in data
        assert isinstance(data["logs"], list)

    async def test_audit_logs_populated(self, client, auth_headers, test_master_data, test_service_data):
        """Audit logs are created during admin operations."""
        # Create service
        service_resp = await client.post(
            "/api/v1/admin/services",
            json={**test_service_data, "master_id": 1},
            headers=auth_headers
        )
        service_id = service_resp.json()["id"]

        # Delete service (creates audit log)
        await client.delete(f"/api/v1/admin/services/{service_id}", headers=auth_headers)

        # Check audit logs
        resp = await client.get("/api/v1/admin/audit-logs", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1  # At least service delete

    async def test_filter_audit_logs_by_entity_type(self, client, auth_headers, test_master_data, test_service_data):
        """Can filter audit logs by entity_type."""
        # Create + delete service
        service_resp = await client.post(
            "/api/v1/admin/services",
            json={**test_service_data, "master_id": 1},
            headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        await client.delete(f"/api/v1/admin/services/{service_id}", headers=auth_headers)

        # Filter by service
        resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"entity_type": "service"},
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert all(log["entity_type"] == "service" for log in data["logs"])

    async def test_audit_logs_pagination(self, client, auth_headers):
        """Audit logs respect limit and offset."""
        resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"limit": 10, "offset": 0},
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["logs"]) <= 10

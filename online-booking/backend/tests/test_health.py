"""Tests for health check endpoints."""


class TestHealthCheck:
    """Tests for GET /health and GET /api/v1/admin/health"""

    async def test_health_check_root(self, client):
        """Root health endpoint returns ok without auth."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "app" in data

    async def test_admin_health_check(self, client, super_admin_headers):
        """Admin health endpoint returns DB and cache status."""
        resp = await client.get("/api/v1/admin/health", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert data["database"] == "connected"
        assert data["status"] in ("healthy", "degraded")

    async def test_admin_health_check_verbose(self, client, super_admin_headers):
        """Verbose health endpoint returns additional metrics."""
        resp = await client.get("/api/v1/admin/health/verbose", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "database" in data
        assert "cache" in data

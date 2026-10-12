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


class TestSecurityHeaders:
    """Hardening headers ride on every response (outermost middleware)."""

    async def test_health_carries_security_headers(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "SAMEORIGIN"
        assert "hsts" not in "".join(r.headers.keys()).lower()  # dev: no HSTS

    async def test_error_responses_carry_cors_and_security_headers(self, client):
        # 404 flows through ExceptionMiddleware (inside CORS): the browser
        # must see ACAO, otherwise it reports a misleading CORS error.
        r = await client.get(
            "/api/v1/masters/999999",
            headers={"Origin": "http://localhost:3000"},
        )
        assert r.status_code == 404
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
        assert r.headers.get("x-content-type-options") == "nosniff"

    async def test_preflight_answered(self, client):
        r = await client.options(
            "/api/v1/admin/notifications/inbox",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        assert r.status_code == 200
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

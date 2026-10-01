"""Tests for admin dashboard and monthly stats endpoints."""
import pytest
from datetime import datetime, timedelta


class TestAdminDashboard:
    """Tests for GET /api/v1/admin/dashboard"""

    async def test_dashboard_empty(self, client, auth_headers):
        """Returns dashboard with zero counts when no data."""
        resp = await client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_appointments"] == 0
        assert data["total_clients"] == 0
        assert data["total_services"] == 0
        assert data["total_revenue"] == 0
        assert isinstance(data["status_counts"], dict)
        assert isinstance(data["recent_appointments"], list)
        assert isinstance(data["upcoming_appointments"], list)

    async def test_dashboard_with_data(self, client, super_admin_headers, test_service_data):
        """Dashboard reflects actual data."""
        # Create service
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=super_admin_headers
        )
        service_id = service_resp.json()["id"]

        resp = await client.get("/api/v1/admin/dashboard", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_services"] >= 1
        assert isinstance(data["status_counts"], dict)
        assert isinstance(data["recent_appointments"], list)


class TestAdminMonthlyStats:
    """Tests for GET /api/v1/admin/monthly-stats"""

    async def test_monthly_stats_empty(self, client, auth_headers):
        """Returns zero stats when no appointments."""
        now = datetime.now()
        resp = await client.get(
            "/api/v1/admin/monthly-stats",
            params={"year": now.year, "month": now.month},
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed_appointments"] == 0
        assert data["total_hours"] == 0
        assert data["revenue"] == 0

    async def test_monthly_stats_with_completed(self, client, super_admin_headers):
        """Monthly stats endpoint works."""
        now = datetime.now()
        resp = await client.get(
            "/api/v1/admin/monthly-stats",
            params={"year": now.year, "month": now.month},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "confirmed_appointments" in data
        assert "total_hours" in data
        assert "revenue" in data

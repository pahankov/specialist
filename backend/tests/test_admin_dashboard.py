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

    async def test_dashboard_with_data(self, client, auth_headers, test_master_data, test_service_data):
        """Dashboard reflects actual data."""
        # Create service
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]

        # Create client
        client_resp = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Dashboard Client", "phone": "+79997778899"},
            headers=auth_headers
        )
        client_id = client_resp.json()["id"]

        # Create completed appointment (for revenue)
        past_date = (datetime.now() - timedelta(days=2)).isoformat()
        await client.post("/api/v1/admin/appointments/book", json={
            "client_id": client_id,
            "service_id": service_id,
            "appointment_date": past_date,
            "status": "completed",
        }, headers=auth_headers)

        # Create pending appointment
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Pending Client",
            "client_phone": "+79998889900",
            "appointment_date": future_date,
        }, headers=auth_headers)

        resp = await client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_appointments"] >= 2
        assert data["total_clients"] >= 1
        assert data["total_services"] >= 1
        assert data["total_revenue"] > 0  # From completed appointment
        assert data["status_counts"].get("completed", 0) >= 1
        assert data["status_counts"].get("pending", 0) >= 1


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

    async def test_monthly_stats_with_completed(self, client, auth_headers, test_master_data, test_service_data):
        """Monthly stats reflect completed appointments."""
        # Create service
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]

        # Create client
        client_resp = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Monthly Client", "phone": "+79990001122"},
            headers=auth_headers
        )
        client_id = client_resp.json()["id"]

        # Create completed appointment in current month
        now = datetime.now()
        current_month_date = now.replace(day=min(now.day, 20))
        await client.post("/api/v1/admin/appointments/book", json={
            "client_id": client_id,
            "service_id": service_id,
            "appointment_date": current_month_date.isoformat(),
            "status": "completed",
        }, headers=auth_headers)

        resp = await client.get(
            "/api/v1/admin/monthly-stats",
            params={"year": now.year, "month": now.month},
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed_appointments"] >= 1
        assert data["total_hours"] > 0
        assert data["revenue"] > 0

"""Tests for schedule module — working hours CRUD endpoints."""
from datetime import date, time


class TestGetWorkingHours:
    """Tests for GET /api/v1/working-hours/"""

    async def test_get_working_hours_empty(self, client, auth_headers):
        """Returns empty list when no working hours."""
        resp = await client.get("/api/v1/working-hours/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_working_hours_with_data(self, client, auth_headers):
        """Returns working hours for authenticated master."""
        # Create working hour first
        await client.post(
            "/api/v1/working-hours/",
            json={
                "master_id": 1,
                "schedule_date": "2026-11-15",
                "start_time": "09:00",
                "end_time": "18:00",
            },
            headers=auth_headers
        )

        resp = await client.get("/api/v1/working-hours/", headers=auth_headers)
        assert resp.status_code == 200
        whs = resp.json()
        assert len(whs) >= 1
        assert whs[0]["master_id"] == 1
        assert whs[0]["schedule_date"] == "2026-11-15"


class TestCreateWorkingHour:
    """Tests for POST /api/v1/working-hours/"""

    async def test_create_working_hour(self, client, auth_headers):
        """Master can create working hours."""
        resp = await client.post(
            "/api/v1/working-hours/",
            json={
                "master_id": 1,
                "schedule_date": "2026-12-01",
                "start_time": "10:00",
                "end_time": "20:00",
            },
            headers=auth_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["master_id"] == 1
        assert data["schedule_date"] == "2026-12-01"
        assert data["start_time"] == "10:00:00"
        assert data["end_time"] == "20:00:00"

    async def test_create_working_hour_wrong_master(self, client, auth_headers):
        """Cannot create working hours for another master."""
        resp = await client.post(
            "/api/v1/working-hours/",
            json={
                "master_id": 999,
                "schedule_date": "2026-12-01",
                "start_time": "10:00",
                "end_time": "18:00",
            },
            headers=auth_headers
        )
        assert resp.status_code == 403

    async def test_create_working_hour_missing_fields(self, client, auth_headers):
        """Returns 422 when required fields are missing."""
        resp = await client.post(
            "/api/v1/working-hours/",
            json={"master_id": 1, "schedule_date": "2026-12-01"},
            headers=auth_headers
        )
        assert resp.status_code == 422


class TestDeleteWorkingHour:
    """Tests for DELETE /api/v1/working-hours/{wh_id}"""

    async def test_delete_working_hour(self, client, auth_headers):
        """Master can delete their own working hour."""
        create_resp = await client.post(
            "/api/v1/working-hours/",
            json={
                "master_id": 1,
                "schedule_date": "2026-12-15",
                "start_time": "09:00",
                "end_time": "18:00",
            },
            headers=auth_headers
        )
        wh_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/working-hours/{wh_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get("/api/v1/working-hours/", headers=auth_headers)
        assert not any(wh["id"] == wh_id for wh in get_resp.json())

    async def test_delete_working_hour_not_found(self, client, auth_headers):
        """Returns 404 for non-existent working hour."""
        resp = await client.delete("/api/v1/working-hours/99999", headers=auth_headers)
        assert resp.status_code == 404

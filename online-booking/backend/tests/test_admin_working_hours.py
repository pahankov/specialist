"""Tests for admin working hours and blocked slots endpoints."""
import pytest
from datetime import datetime, timedelta


class TestAdminGetWorkingHours:
    """Tests for GET /api/v1/admin/working-hours"""

    async def test_get_working_hours_empty(self, client, auth_headers):
        """Returns empty list when no working hours."""
        resp = await client.get("/api/v1/admin/working-hours", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_working_hours_with_data(self, client, auth_headers):
        """Returns working hours."""
        await client.post(
            "/api/v1/admin/working-hours",
            json={
                "schedule_date": "2026-10-01",
                "start_time": "09:00",
                "end_time": "18:00",
            },
            headers=auth_headers
        )

        resp = await client.get("/api/v1/admin/working-hours", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestAdminCreateWorkingHour:
    """Tests for POST /api/v1/admin/working-hours"""

    async def test_create_working_hour(self, client, auth_headers):
        """Admin can create working hours."""
        resp = await client.post(
            "/api/v1/admin/working-hours",
            json={
                "schedule_date": "2026-11-15",
                "start_time": "10:00",
                "end_time": "20:00",
            },
            headers=auth_headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["schedule_date"] == "2026-11-15"
        assert data["start_time"] == "10:00:00"
        assert data["end_time"] == "20:00:00"

    async def test_create_working_hour_missing_fields(self, client, auth_headers):
        """Returns 422 when required fields are missing."""
        resp = await client.post(
            "/api/v1/admin/working-hours",
            json={"schedule_date": "2026-11-15"},
            headers=auth_headers
        )
        assert resp.status_code == 422


class TestAdminUpdateWorkingHour:
    """Tests for PATCH /api/v1/admin/working-hours/{id}"""

    async def test_update_working_hour(self, client, auth_headers):
        """Admin can update working hours."""
        create_resp = await client.post(
            "/api/v1/admin/working-hours",
            json={
                "schedule_date": "2026-12-01",
                "start_time": "09:00",
                "end_time": "18:00",
            },
            headers=auth_headers
        )
        wh_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/admin/working-hours/{wh_id}",
            json={"start_time": "10:00", "end_time": "19:00"},
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["start_time"] == "10:00:00"
        assert resp.json()["end_time"] == "19:00:00"

    async def test_update_working_hour_not_found(self, client, auth_headers):
        """Returns 404 for non-existent working hour."""
        resp = await client.patch(
            "/api/v1/admin/working-hours/99999",
            json={"start_time": "10:00"},
            headers=auth_headers
        )
        assert resp.status_code == 404


class TestAdminDeleteWorkingHour:
    """Tests for DELETE /api/v1/admin/working-hours/{id}"""

    async def test_delete_working_hour(self, client, auth_headers):
        """Admin can delete working hours."""
        create_resp = await client.post(
            "/api/v1/admin/working-hours",
            json={
                "schedule_date": "2026-12-15",
                "start_time": "09:00",
                "end_time": "18:00",
            },
            headers=auth_headers
        )
        wh_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/admin/working-hours/{wh_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get("/api/v1/admin/working-hours", headers=auth_headers)
        assert not any(wh["id"] == wh_id for wh in get_resp.json())


class TestAdminBlockedSlots:
    """Tests for admin blocked slots endpoints"""

    async def test_get_blocked_slots_empty(self, client, auth_headers):
        """Returns empty list when no blocked slots."""
        resp = await client.get("/api/v1/admin/blocked-slots", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_create_blocked_slot(self, client, auth_headers):
        """Admin can create a blocked slot."""
        now = datetime.now()
        start_dt = now + timedelta(days=1)
        end_dt = now + timedelta(days=2)

        resp = await client.post(
            "/api/v1/admin/blocked-slots",
            json={
                "master_id": 1,
                "start_dt": start_dt.isoformat(),
                "end_dt": end_dt.isoformat(),
                "reason": "Выходной",
            },
            headers=auth_headers
        )
        assert resp.status_code == 201
        assert resp.json()["reason"] == "Выходной"

    async def test_create_blocked_slot_invalid_dates(self, client, auth_headers):
        """Returns 422 when start_dt >= end_dt."""
        now = datetime.now()
        resp = await client.post(
            "/api/v1/admin/blocked-slots",
            json={
                "master_id": 1,
                "start_dt": (now + timedelta(days=2)).isoformat(),
                "end_dt": (now + timedelta(days=1)).isoformat(),
            },
            headers=auth_headers
        )
        assert resp.status_code == 422

    async def test_delete_blocked_slot(self, client, auth_headers):
        """Admin can delete a blocked slot."""
        now = datetime.now()
        create_resp = await client.post(
            "/api/v1/admin/blocked-slots",
            json={
                "master_id": 1,
                "start_dt": (now + timedelta(days=1)).isoformat(),
                "end_dt": (now + timedelta(days=2)).isoformat(),
            },
            headers=auth_headers
        )
        slot_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/admin/blocked-slots/{slot_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get("/api/v1/admin/blocked-slots", headers=auth_headers)
        assert not any(s["id"] == slot_id for s in get_resp.json())

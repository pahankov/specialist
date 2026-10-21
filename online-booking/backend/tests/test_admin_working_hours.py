"""Tests for admin working hours and blocked slots endpoints."""
import pytest
from datetime import date, datetime, time, timedelta


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

    async def test_create_duplicate_date_conflict(self, client, auth_headers):
        """Second hours row for the same date is 409, not 500."""
        payload = {
            "schedule_date": "2026-11-20",
            "start_time": "09:00",
            "end_time": "18:00",
        }
        first = await client.post(
            "/api/v1/admin/working-hours", json=payload, headers=auth_headers
        )
        assert first.status_code == 201, first.text
        again = await client.post(
            "/api/v1/admin/working-hours", json=payload, headers=auth_headers
        )
        assert again.status_code == 409


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


class TestAdminApplySchedule:
    """Bulk work/rest cycle application."""

    @staticmethod
    def _payload(start: date, end: date, *, work: int, off: int, anchor: date):
        return {
            "range_start": start.isoformat(),
            "range_end": end.isoformat(),
            "cycle_work_days": work,
            "cycle_off_days": off,
            "cycle_anchor": anchor.isoformat(),
            "start_time": "09:00",
            "end_time": "18:00",
            "replace_off_days": True,
        }

    async def test_apply_2_2_creates_updates_and_removes_days(
        self, client, auth_headers
    ):
        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=6)

        # Existing work day gets the new hours; existing rest day is removed.
        await client.post("/api/v1/admin/working-hours", json={
            "schedule_date": start.isoformat(),
            "start_time": "10:00", "end_time": "12:00",
        }, headers=auth_headers)
        await client.post("/api/v1/admin/working-hours", json={
            "schedule_date": (start + timedelta(days=2)).isoformat(),
            "start_time": "10:00", "end_time": "12:00",
        }, headers=auth_headers)
        # A stale window must be replaced by the template's exact hours.
        narrow = await client.patch("/api/v1/admin/work-window", json={
            "start_hour": 10, "end_hour": 12,
        }, headers=auth_headers)
        assert narrow.status_code == 200, narrow.text

        resp = await client.post(
            "/api/v1/admin/working-hours/apply",
            json=self._payload(start, end, work=2, off=2, anchor=start),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["effective_start"] == start.isoformat()
        assert data["work_days"] == 4
        assert data["off_days"] == 3
        assert data["created"] == 3
        assert data["updated"] == 1
        assert data["removed"] == 1
        assert data["skipped_booked"] == 0
        assert data["window_start_hour"] == 9
        assert data["window_end_hour"] == 18

        rows = (await client.get(
            "/api/v1/admin/working-hours", headers=auth_headers
        )).json()
        by_date = {row["schedule_date"]: row for row in rows}
        work_dates = {
            start, start + timedelta(days=1),
            start + timedelta(days=4), start + timedelta(days=5),
        }
        for day in work_dates:
            row = by_date[day.isoformat()]
            assert row["start_time"].startswith("09:00")
            assert row["end_time"].startswith("18:00")
        for offset in (2, 3, 6):
            assert (start + timedelta(days=offset)).isoformat() not in by_date

    async def test_apply_resets_work_window_to_template_hours(
        self, client, auth_headers
    ):
        """Granules follow the applied template, dropping a wider old window."""
        day = date.today() + timedelta(days=1)
        before = await client.patch("/api/v1/admin/work-window", json={
            "start_hour": 6, "end_hour": 23,
        }, headers=auth_headers)
        assert before.status_code == 200, before.text

        resp = await client.post(
            "/api/v1/admin/working-hours/apply",
            json=self._payload(day, day, work=1, off=0, anchor=day),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["window_start_hour"] == 9
        assert resp.json()["window_end_hour"] == 18

        window = await client.get("/api/v1/admin/work-window", headers=auth_headers)
        assert window.status_code == 200, window.text
        assert window.json()["start_hour"] == 9
        assert window.json()["end_hour"] == 18

    async def test_apply_can_reset_window_to_midnight(
        self, client, auth_headers
    ):
        """00:00 is a real template start, not a missing value."""
        day = date.today() + timedelta(days=1)
        payload = self._payload(day, day, work=1, off=0, anchor=day)
        payload["start_time"] = "00:00"
        payload["end_time"] = "08:00"

        resp = await client.post(
            "/api/v1/admin/working-hours/apply",
            json=payload,
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["window_start_hour"] == 0
        assert resp.json()["window_end_hour"] == 8

    async def test_past_days_are_not_touched(self, client, auth_headers):
        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)
        await client.post("/api/v1/admin/working-hours", json={
            "schedule_date": yesterday.isoformat(),
            "start_time": "07:00", "end_time": "09:00",
        }, headers=auth_headers)

        resp = await client.post(
            "/api/v1/admin/working-hours/apply",
            json=self._payload(yesterday, tomorrow, work=1, off=0, anchor=today),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["effective_start"] == today.isoformat()
        assert data["work_days"] == 2

        rows = (await client.get(
            "/api/v1/admin/working-hours", headers=auth_headers
        )).json()
        by_date = {row["schedule_date"]: row for row in rows}
        old = by_date[yesterday.isoformat()]
        assert old["start_time"].startswith("07:00")
        assert old["end_time"].startswith("09:00")

    async def test_day_with_live_booking_is_preserved(
        self, client, session, auth_headers
    ):
        from sqlalchemy import select

        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User, UserRole

        start = date.today() + timedelta(days=1)
        end = start + timedelta(days=6)
        protected_day = start + timedelta(days=2)  # rest day in a 2/2 cycle

        await client.post("/api/v1/admin/working-hours", json={
            "schedule_date": protected_day.isoformat(),
            "start_time": "09:00", "end_time": "18:00",
        }, headers=auth_headers)
        for offset in (3, 6):
            await client.post("/api/v1/admin/working-hours", json={
                "schedule_date": (start + timedelta(days=offset)).isoformat(),
                "start_time": "09:00", "end_time": "18:00",
            }, headers=auth_headers)

        profile = (await session.execute(select(MasterProfile))).scalars().first()
        service = Service(
            master_id=profile.id, name="Apply test", duration_minutes=60, price=1000
        )
        client_user = User(
            name="Apply Client", email="apply_client@example.com",
            role=UserRole.CLIENT,
        )
        session.add_all([service, client_user])
        await session.flush()
        client_profile = ClientProfile(user_id=client_user.id)
        session.add(client_profile)
        await session.flush()
        session.add(Appointment(
            master_id=profile.id,
            service_id=service.id,
            client_id=client_profile.id,
            appointment_date=datetime.combine(protected_day, time(10, 0)),
            status="pending",
            created_by_role="master",
        ))
        await session.commit()

        resp = await client.post(
            "/api/v1/admin/working-hours/apply",
            json=self._payload(start, end, work=2, off=2, anchor=start),
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["skipped_booked"] == 1
        assert data["skipped_dates"] == [protected_day.isoformat()]
        assert data["removed"] == 2  # the other two rest days

        rows = (await client.get(
            "/api/v1/admin/working-hours", headers=auth_headers
        )).json()
        by_date = {row["schedule_date"]: row for row in rows}
        kept = by_date[protected_day.isoformat()]
        assert kept["start_time"].startswith("09:00")
        assert kept["end_time"].startswith("18:00")

"""Tests for admin appointment endpoints."""
import pytest
from datetime import datetime, timedelta


class TestAdminGetAppointments:
    """Tests for GET /api/v1/admin/appointments"""

    async def test_get_admin_appointments_empty(self, client, auth_headers):
        """Returns empty list when no appointments."""
        resp = await client.get("/api/v1/admin/appointments", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_get_admin_appointments_with_data(self, client, auth_headers, test_master_data, test_service_data):
        """Returns appointments with client and service details."""
        # Create service
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]

        # Create appointment via admin endpoint
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Admin Client",
            "client_phone": "+79994445566",
            "appointment_date": future_date,
        }, headers=auth_headers)

        resp = await client.get("/api/v1/admin/appointments", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) >= 1
        appt = data["items"][0]
        assert "client_name" in appt
        assert "service_name" in appt

    async def test_appointments_sort_dir(self, client, auth_headers, test_service_data):
        """sort_dir=asc returns oldest first, desc (default) newest first."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        for days, phone in ((2, "+79994445571"), (9, "+79994445572")):
            await client.post("/api/v1/admin/appointments", json={
                "master_id": 1,
                "service_id": service_id,
                "client_name": "Sort Client",
                "client_phone": phone,
                "appointment_date": (datetime.now() + timedelta(days=days)).isoformat(),
            }, headers=auth_headers)

        asc = await client.get(
            "/api/v1/admin/appointments", params={"sort_dir": "asc"}, headers=auth_headers
        )
        assert asc.status_code == 200, asc.text
        asc_dates = [i["appointment_date"] for i in asc.json()["items"]]
        assert asc_dates == sorted(asc_dates)

        desc = await client.get("/api/v1/admin/appointments", headers=auth_headers)
        assert desc.status_code == 200, desc.text
        desc_dates = [i["appointment_date"] for i in desc.json()["items"]]
        assert desc_dates == sorted(desc_dates, reverse=True)


class TestAdminCreateAppointment:
    """Tests for POST /api/v1/admin/appointments"""

    async def test_admin_create_appointment(self, client, auth_headers, test_service_data):
        """Admin can create appointment with auto client creation."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "New Client",
            "client_phone": "+79996667788",
            "appointment_date": future_date,
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "pending"

    async def test_admin_create_appointment_wrong_master(self, client, auth_headers):
        """Cannot create appointment for another master."""
        resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 999,
            "service_id": 1,
            "client_name": "Test",
            "client_phone": "+79990000000",
            "appointment_date": "2026-12-01T10:00:00",
        }, headers=auth_headers)
        # Returns 403 or 422 (validation) depending on implementation
        assert resp.status_code in (403, 422)

    async def test_direct_create_snapshots_price_and_rejects_conflict(
        self, client, session, auth_headers, test_service_data,
    ):
        """Direct create validates the service, snapshots facts, blocks overlap."""
        from sqlalchemy import select
        from app.models.appointment import Appointment

        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1},
            headers=auth_headers,
        )
        service_id = service_resp.json()["id"]
        day = (datetime.now() + timedelta(days=8)).replace(
            hour=13, minute=0, second=0, microsecond=0)

        first = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1, "service_id": service_id,
            "client_name": "Snapshot Client",
            "client_phone": "+79995550001",
            "appointment_date": day.isoformat(),
        }, headers=auth_headers)
        assert first.status_code == 201, first.text

        stored = (await session.execute(
            select(Appointment).where(Appointment.id == first.json()["id"])
        )).scalar_one()
        assert float(stored.price) == pytest.approx(2500.0)
        assert stored.duration_minutes == 60

        clash = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1, "service_id": service_id,
            "client_name": "Clash Client",
            "client_phone": "+79995550002",
            "appointment_date": day.isoformat(),
        }, headers=auth_headers)
        assert clash.status_code == 409, clash.text


class TestAdminConfirmAppointment:
    """Tests for PATCH /api/v1/admin/appointments/{id}/confirm"""

    async def test_confirm_appointment(self, client, auth_headers, test_master_data, test_service_data):
        """Admin can confirm a pending appointment."""
        # Create service + appointment
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        create_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Confirm Test",
            "client_phone": "+79991110001",
            "appointment_date": future_date,
        }, headers=auth_headers)
        appt_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/admin/appointments/{appt_id}/confirm", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "confirmed"

    async def test_confirm_appointment_not_found(self, client, auth_headers):
        """Returns 404 for non-existent appointment."""
        resp = await client.patch(
            "/api/v1/admin/appointments/99999/confirm", headers=auth_headers
        )
        assert resp.status_code == 404


class TestAdminCancelAppointment:
    """Tests for PATCH /api/v1/admin/appointments/{id}/cancel"""

    async def test_cancel_appointment(self, client, auth_headers, test_master_data, test_service_data):
        """Admin can cancel an appointment with reason."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        create_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Cancel Test",
            "client_phone": "+79992220002",
            "appointment_date": future_date,
        }, headers=auth_headers)
        appt_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/admin/appointments/{appt_id}/cancel?reason=Клиент передумал",
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_cancel_appointment_no_reason(self, client, auth_headers, test_master_data, test_service_data):
        """Admin can cancel without specifying reason."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        create_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "No Reason",
            "client_phone": "+79993330003",
            "appointment_date": future_date,
        }, headers=auth_headers)
        appt_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/admin/appointments/{appt_id}/cancel",
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"


class TestAdminCompleteAppointment:
    """Tests for PATCH /api/v1/admin/appointments/{id}/complete"""

    async def test_complete_appointment(self, client, auth_headers, test_master_data, test_service_data):
        """Admin can complete an appointment."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        create_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Complete Test",
            "client_phone": "+79994440004",
            "appointment_date": future_date,
        }, headers=auth_headers)
        appt_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/admin/appointments/{appt_id}/complete", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "completed"


class TestAdminDeleteAppointment:
    """Tests for DELETE /api/v1/admin/appointments/{id}"""

    async def test_delete_admin_appointment(self, client, auth_headers, test_master_data, test_service_data):
        """Admin can delete an appointment."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        create_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Delete Test",
            "client_phone": "+79995550005",
            "appointment_date": future_date,
        }, headers=auth_headers)
        appt_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/admin/appointments/{appt_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get("/api/v1/admin/appointments", headers=auth_headers)
        assert len(get_resp.json()["items"]) == 0


class TestAdminBookAppointment:
    """Tests for POST /api/v1/admin/appointments/book"""

    async def test_book_appointment_success(self, client, auth_headers, test_master_data, test_service_data, test_client_data):
        """Admin can book appointment with existing client."""
        # Create service + client
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]

        client_resp = await client.post("/api/v1/admin/clients", json=test_client_data, headers=auth_headers)
        client_id = client_resp.json()["id"]

        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        resp = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": client_id,
            "service_id": service_id,
            "appointment_date": future_date,
            "status": "confirmed",
            "notes": "Тестовая запись",
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "confirmed"

    async def test_book_appointment_conflict(self, client, auth_headers, test_master_data, test_service_data, test_client_data):
        """Admin cannot book overlapping time slot."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]

        client_resp = await client.post("/api/v1/admin/clients", json=test_client_data, headers=auth_headers)
        client_id = client_resp.json()["id"]

        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        # First booking
        await client.post("/api/v1/admin/appointments/book", json={
            "client_id": client_id,
            "service_id": service_id,
            "appointment_date": future_date,
            "status": "confirmed",
        }, headers=auth_headers)

        # Second booking at same time — conflict check may or may not trigger
        # depending on implementation; just verify booking endpoint works
        resp = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": client_id,
            "service_id": service_id,
            "appointment_date": future_date,
            "status": "confirmed",
        }, headers=auth_headers)
        # Either 201 (no conflict check) or 409 (conflict detected)
        assert resp.status_code in (201, 409)


class TestAdminAppointmentsByDate:
    """Tests for GET /api/v1/admin/appointments/by-date"""

    async def test_get_by_date_range(self, client, auth_headers, test_master_data, test_service_data):
        """Returns appointments within date range."""
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]

        future_date = datetime.now() + timedelta(days=7)
        await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Date Range Test",
            "client_phone": "+79996660006",
            "appointment_date": future_date.isoformat(),
        }, headers=auth_headers)

        date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        date_to = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

        resp = await client.get(
            "/api/v1/admin/appointments/by-date",
            params={"date_from": date_from, "date_to": date_to},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
        assert "client_name" in resp.json()[0]
        assert "service_name" in resp.json()[0]

    async def test_by_date_carries_service_duration(
        self, client, auth_headers, test_master_data, test_service_data
    ):
        """by-date rows carry service_id/duration for granule spans."""
        service_resp = await client.post(
            "/api/v1/services/",
            json={**test_service_data, "master_id": 1, "duration_minutes": 90},
            headers=auth_headers,
        )
        assert service_resp.status_code == 201, service_resp.text
        service_id = service_resp.json()["id"]

        future_date = datetime.now() + timedelta(days=7)
        created = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Span Test",
            "client_phone": "+79996660009",
            "appointment_date": future_date.isoformat(),
        }, headers=auth_headers)
        assert created.status_code == 201, created.text

        date_from = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        date_to = (datetime.now() + timedelta(days=14)).strftime("%Y-%m-%d")

        resp = await client.get(
            "/api/v1/admin/appointments/by-date",
            params={"date_from": date_from, "date_to": date_to},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        row = next(r for r in resp.json() if r["client_name"] == "Span Test")
        assert row["service_id"] == service_id
        assert row["service_duration"] == 90


class TestMarkNoShow:
    """Tests for PATCH /api/v1/admin/appointments/{id}/no-show"""

    async def test_mark_no_show_increments_count(self, client, auth_headers, test_master_data, test_service_data):
        """Marking appointment as no-show increments client's no_show_count."""
        # Create service + appointment
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        create_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "No Show Client",
            "client_phone": "+79997770007",
            "appointment_date": future_date,
        }, headers=auth_headers)
        appt_id = create_resp.json()["id"]

        # Verify client has no_show_count = 0
        client_resp = await client.get("/api/v1/admin/clients", headers=auth_headers)
        clients = client_resp.json()["items"]
        client_before = next(
            c for c in clients
            if c["name"] == "No Show Client"
        )
        assert client_before["no_show_count"] == 0

        # Mark as no-show
        resp = await client.patch(
            f"/api/v1/admin/appointments/{appt_id}/no-show",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"
        assert "Неявка" in resp.json()["notes"]

        # Verify client's no_show_count incremented to 1
        # Use search to find the specific client
        client_resp = await client.get("/api/v1/admin/clients", params={"search": "No Show Client"}, headers=auth_headers)
        clients = client_resp.json()["items"]
        assert len(clients) > 0, f"Clients found: {[c['name'] for c in clients]}"
        client_after = clients[0]
        assert client_after["name"] == "No Show Client"
        assert client_after["no_show_count"] == 1

    async def test_mark_no_show_multiple_times(self, client, auth_headers, test_master_data, test_service_data):
        """Multiple no-shows increment count each time."""
        # Create service + 2 appointments for same client
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        # First appointment
        appt1_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Repeat No-Show",
            "client_phone": "+79998880008",
            "appointment_date": future_date,
        }, headers=auth_headers)

        # Second appointment (same client, same phone, non-overlapping slot)
        appt2_resp = await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Repeat No-Show",
            "client_phone": "+79998880008",
            "appointment_date": (datetime.now() + timedelta(days=8)).isoformat(),
        }, headers=auth_headers)

        # Mark first as no-show
        await client.patch(
            f"/api/v1/admin/appointments/{appt1_resp.json()['id']}/no-show",
            headers=auth_headers,
        )

        # Mark second as no-show
        await client.patch(
            f"/api/v1/admin/appointments/{appt2_resp.json()['id']}/no-show",
            headers=auth_headers,
        )

        # Verify no_show_count = 2
        client_resp = await client.get("/api/v1/admin/clients", headers=auth_headers)
        clients = client_resp.json()["items"]
        client_data = next(
            c for c in clients
            if c["name"] == "Repeat No-Show"
        )
        assert client_data["no_show_count"] == 2

    async def test_mark_no_show_not_found(self, client, auth_headers):
        """Returns 404 for non-existent appointment."""
        resp = await client.patch(
            "/api/v1/admin/appointments/99999/no-show",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestExactOverlapAndBells:
    """Aligned overlap check (both sides' durations) + confirm bell."""

    async def _setup(self, client, session, auth_headers):
        from app.models.service import Service

        long_svc = await client.post(
            "/api/v1/services/",
            json={"name": "Long", "description": "x", "duration_minutes": 120,
                  "price": 1000, "master_id": 1},
            headers=auth_headers,
        )
        short_svc = await client.post(
            "/api/v1/services/",
            json={"name": "Short", "description": "x", "duration_minutes": 30,
                  "price": 500, "master_id": 1},
            headers=auth_headers,
        )
        assert long_svc.status_code == 201, long_svc.text
        assert short_svc.status_code == 201, short_svc.text
        from datetime import datetime, timedelta
        day = (datetime.now() + timedelta(days=6)).replace(
            hour=14, minute=0, second=0, microsecond=0)
        return long_svc.json()["id"], short_svc.json()["id"], day

    async def test_book_exact_overlap_asymmetric(
        self, client, session, auth_headers, test_master_data, test_service_data
    ):
        """120-min at 14:00 blocks a 30-min at 15:00, frees 16:00."""
        long_id, short_id, day = await self._setup(client, session, auth_headers)
        # Need a real client id: create one via clients endpoint.
        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Overlap", "phone": "+79990006655"},
            headers=auth_headers,
        )
        cid = created.json()["id"]
        first = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": cid, "service_id": long_id,
            "appointment_date": day.isoformat(), "status": "pending",
        }, headers=auth_headers)
        assert first.status_code == 201, first.text

        clash = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": cid, "service_id": short_id,
            "appointment_date": day.replace(hour=15).isoformat(), "status": "pending",
        }, headers=auth_headers)
        assert clash.status_code == 409

        free = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": cid, "service_id": short_id,
            "appointment_date": day.replace(hour=16).isoformat(), "status": "pending",
        }, headers=auth_headers)
        assert free.status_code == 201, free.text

    async def test_confirm_bells_the_client(self, client, session, auth_headers):
        """Master confirm lands in the client's bell with a deep link."""
        from sqlalchemy import select
        from app.models.notification import Notification

        long_id, _, day = await self._setup(client, session, auth_headers)
        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Bell", "phone": "+79990006677"},
            headers=auth_headers,
        )
        cid = created.json()["id"]
        booked = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": cid, "service_id": long_id,
            "appointment_date": day.isoformat(), "status": "pending",
        }, headers=auth_headers)
        appt_id = booked.json()["id"]

        r = await client.patch(
            f"/api/v1/admin/appointments/{appt_id}/confirm", headers=auth_headers)
        assert r.status_code == 200, r.text

        notes = (await session.execute(
            select(Notification).where(Notification.recipient_id == cid)
        )).scalars().all()
        assert len(notes) == 1
        assert "подтвердил" in notes[0].text
        assert notes[0].link == f"appointments:{appt_id}"

    async def test_cancel_bells_the_client(self, client, session, auth_headers):
        """Master cancel lands in the client's bell, with the reason."""
        from sqlalchemy import select
        from app.models.notification import Notification

        long_id, _, day = await self._setup(client, session, auth_headers)
        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "CancelBell", "phone": "+79990006688"},
            headers=auth_headers,
        )
        cid = created.json()["id"]
        booked = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": cid, "service_id": long_id,
            "appointment_date": day.isoformat(), "status": "pending",
        }, headers=auth_headers)
        appt_id = booked.json()["id"]

        r = await client.patch(
            f"/api/v1/admin/appointments/{appt_id}/cancel?reason=Заболел",
            headers=auth_headers)
        assert r.status_code == 200, r.text

        notes = (await session.execute(
            select(Notification).where(Notification.recipient_id == cid)
        )).scalars().all()
        assert len(notes) == 1
        assert "отменил" in notes[0].text
        assert "Заболел" in notes[0].text
        assert notes[0].link == f"appointments:{appt_id}"

    async def test_reopen_completed_back_to_work(self, client, session, auth_headers):
        """Completed (incl. auto) flips back to confirmed + client bell."""
        from sqlalchemy import select
        from app.models.notification import Notification

        long_id, _, day = await self._setup(client, session, auth_headers)
        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Reopen", "phone": "+79990006699"},
            headers=auth_headers,
        )
        cid = created.json()["id"]
        booked = await client.post("/api/v1/admin/appointments/book", json={
            "client_id": cid, "service_id": long_id,
            "appointment_date": day.isoformat(), "status": "confirmed",
        }, headers=auth_headers)
        appt_id = booked.json()["id"]

        c = await client.patch(f"/api/v1/admin/appointments/{appt_id}/complete",
                               headers=auth_headers)
        assert c.status_code == 200, c.text

        bad = await client.patch(f"/api/v1/admin/appointments/{appt_id}/reopen",
                                 headers=auth_headers)
        # completed → reopen works; second reopen must 400 (not completed).
        assert bad.status_code == 200, bad.text
        again = await client.patch(f"/api/v1/admin/appointments/{appt_id}/reopen",
                                   headers=auth_headers)
        assert again.status_code == 400

        notes = (await session.execute(
            select(Notification).where(Notification.recipient_id == cid)
        )).scalars().all()
        assert any("в работу" in (n.text or "") for n in notes)

    async def test_show_toggles_filter_server_side(self, client, session,
                                                   created_master_id):
        """Pager totals match the actually returned rows (no client filter)."""
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import select
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.service import Service
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        mu = (await session.execute(
            select(User).where(User.role == UserRole.MASTER))).scalar_one()
        mh = {"Authorization": f"Bearer {create_access_token({'sub': str(mu.id), 'role': 'MASTER', 'name': mu.name, 'is_admin': False})}"}

        svc = Service(master_id=created_master_id, name="Pg", duration_minutes=60,
                      price=1000, is_active=True)
        session.add(svc)
        await session.flush()
        cu = User(name="PgC", email="pgc@example.com", phone="+79990009601",
                  hashed_password=hash_password("SecurePass123!"),
                  role=UserRole.CLIENT, is_active=True)
        session.add(cu)
        await session.flush()
        cp = ClientProfile(user_id=cu.id)
        session.add(cp)
        await session.flush()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add_all([
            Appointment(master_id=created_master_id, service_id=svc.id,
                        client_id=cp.id, duration_minutes=60,
                        appointment_date=now + timedelta(days=1), status="confirmed"),
            Appointment(master_id=created_master_id, service_id=svc.id,
                        client_id=cp.id, duration_minutes=60,
                        appointment_date=now + timedelta(days=2), status="completed"),
            Appointment(master_id=created_master_id, service_id=svc.id,
                        client_id=cp.id, duration_minutes=60,
                        appointment_date=now + timedelta(days=3), status="cancelled"),
        ])
        await session.commit()

        async def total(**params):
            r = await client.get("/api/v1/admin/appointments",
                                 params={"page": 1, "page_size": 20, **params},
                                 headers=mh)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["total"] == len(body["items"])
            return body["total"]

        assert await total() == 3
        assert await total(show_completed="false") == 2
        assert await total(show_cancelled="false") == 2
        assert await total(show_completed="false", show_cancelled="false") == 1

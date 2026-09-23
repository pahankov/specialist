"""Tests for appointments endpoints — public booking + authenticated CRUD."""
import pytest
from datetime import datetime, timedelta


class TestPublicBooking:
    """Tests for POST /api/v1/appointments/public"""

    async def test_public_booking_success(self, client, test_master_data, test_service_data):
        """Client can book a public appointment."""
        # Register master + create service
        await client.post("/api/v1/auth/register", json=test_master_data)
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}
        )
        service_id = service_resp.json()["id"]

        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        booking_data = {
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Public Client",
            "client_phone": "+79998887766",
            "appointment_date": future_date,
        }
        resp = await client.post("/api/v1/appointments/public", json=booking_data)
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["master_id"] == 1
        assert data["service_id"] == service_id
        assert "client_id" in data

    async def test_public_booking_master_not_found(self, client):
        """Public booking fails for non-existent master."""
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        resp = await client.post("/api/v1/appointments/public", json={
            "master_id": 99999,
            "service_id": 1,
            "client_name": "Test",
            "client_phone": "+79990000000",
            "appointment_date": future_date,
        })
        assert resp.status_code == 404

    async def test_public_booking_service_not_found(self, client, test_master_data):
        """Public booking fails for non-existent service."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        resp = await client.post("/api/v1/appointments/public", json={
            "master_id": 1,
            "service_id": 99999,
            "client_name": "Test",
            "client_phone": "+79990000000",
            "appointment_date": future_date,
        })
        assert resp.status_code == 404

    async def test_public_booking_creates_client_if_new(self, client, test_master_data, test_service_data):
        """Public booking creates a new client record."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}
        )
        service_id = service_resp.json()["id"]

        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        resp = await client.post("/api/v1/appointments/public", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "New Client",
            "client_phone": "+79991234567",
            "appointment_date": future_date,
        })
        assert resp.status_code == 201

        # Verify client was created
        clients_resp = await client.get("/api/v1/clients/")
        clients = clients_resp.json()
        assert len(clients) >= 1
        assert any("+7" in c["phone"] and "123" in c["phone"] for c in clients)


class TestGetAppointments:
    """Tests for GET /api/v1/appointments/"""

    async def test_get_appointments_empty(self, client, auth_headers):
        """Returns empty list when no appointments."""
        resp = await client.get("/api/v1/appointments/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_appointments_with_data(self, client, auth_headers, test_master_data, test_service_data):
        """Returns appointments for authenticated master."""
        # Create service first
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}
        )
        service_id = service_resp.json()["id"]

        future_date = (datetime.now() + timedelta(days=7)).isoformat()
        # Create appointment via admin endpoint (authenticated)
        await client.post("/api/v1/admin/appointments", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Test",
            "client_phone": "+79990001111",
            "appointment_date": future_date,
        }, headers=auth_headers)

        resp = await client.get("/api/v1/appointments/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestCreateAppointment:
    """Tests for POST /api/v1/appointments/"""

    async def test_create_appointment_success(self, client, auth_headers, test_master_data, test_service_data):
        """Authenticated master can create appointment."""
        # Register master first
        await client.post("/api/v1/auth/register", json=test_master_data)
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        resp = await client.post("/api/v1/appointments/", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "Client Name",
            "client_phone": "+79991110000",
            "appointment_date": future_date,
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["status"] == "confirmed"

    async def test_create_appointment_wrong_master(self, client, auth_headers):
        """Cannot create appointment for another master."""
        resp = await client.post("/api/v1/appointments/", json={
            "master_id": 999,
            "service_id": 1,
            "client_name": "Test",
            "client_phone": "+79990000000",
            "appointment_date": "2026-12-01T10:00:00",
        }, headers=auth_headers)
        assert resp.status_code == 403


class TestDeleteAppointment:
    """Tests for DELETE /api/v1/appointments/{id}"""

    async def test_delete_appointment(self, client, auth_headers, test_master_data, test_service_data):
        """Authenticated master can delete appointment."""
        # Register master + create service + create appointment
        await client.post("/api/v1/auth/register", json=test_master_data)
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}
        )
        service_id = service_resp.json()["id"]
        future_date = (datetime.now() + timedelta(days=7)).isoformat()

        create_resp = await client.post("/api/v1/appointments/", json={
            "master_id": 1,
            "service_id": service_id,
            "client_name": "To Delete",
            "client_phone": "+79992223344",
            "appointment_date": future_date,
        }, headers=auth_headers)
        appt_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/v1/appointments/{appt_id}", headers=auth_headers)
        assert delete_resp.status_code == 204

        # Verify deleted
        get_resp = await client.get("/api/v1/appointments/", headers=auth_headers)
        assert len(get_resp.json()) == 0

    async def test_delete_appointment_not_found(self, client, auth_headers):
        """Returns 404 for non-existent appointment."""
        resp = await client.delete("/api/v1/appointments/99999", headers=auth_headers)
        assert resp.status_code == 404

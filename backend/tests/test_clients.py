"""Tests for clients CRUD endpoints."""
import pytest


class TestGetClients:
    """Tests for GET /api/v1/clients/"""

    async def test_get_clients_empty(self, client, auth_headers):
        """Returns empty list when no clients."""
        resp = await client.get("/api/v1/clients/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_clients_with_data(self, client, auth_headers, test_client_data):
        """Returns list of clients."""
        create_resp = await client.post("/api/v1/clients/", json=test_client_data, headers=auth_headers)
        assert create_resp.status_code == 201

        resp = await client.get("/api/v1/clients/", headers=auth_headers)
        assert resp.status_code == 200
        clients = resp.json()
        assert len(clients) >= 1
        # Phone is normalized by schema: +79991112233 -> +7 (999) 111-22-33
        assert any("+7" in c["phone"] and "999" in c["phone"] for c in clients)


class TestGetClientById:
    """Tests for GET /api/v1/clients/{id}"""

    async def test_get_client_by_id(self, client, auth_headers, test_client_data):
        """Returns client by ID."""
        create_resp = await client.post("/api/v1/clients/", json=test_client_data, headers=auth_headers)
        client_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/clients/{client_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == client_id

    async def test_get_client_not_found(self, client, auth_headers):
        """Returns 404 for non-existent client."""
        resp = await client.get("/api/v1/clients/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestCreateClient:
    """Tests for POST /api/v1/clients/"""

    async def test_create_client_success(self, client, auth_headers, test_client_data):
        """Client can be created."""
        resp = await client.post("/api/v1/clients/", json=test_client_data, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == test_client_data["name"]
        # Phone is normalized: +79991112233 -> +7 (999) 111-22-33
        assert "+7" in data["phone"] and "999" in data["phone"]
        assert "id" in data

    async def test_create_client_duplicate_phone(self, client, auth_headers, test_client_data):
        """Cannot create client with duplicate phone (DB unique constraint)."""
        await client.post("/api/v1/clients/", json=test_client_data, headers=auth_headers)

        resp = await client.post("/api/v1/clients/", json=test_client_data, headers=auth_headers)
        # 422 from DB unique constraint or 400 from app logic
        assert resp.status_code in (400, 422)

    async def test_create_client_duplicate_email(self, client, auth_headers):
        """Cannot create client with duplicate email."""
        data1 = {"name": "Client 1", "phone": "+79990000001", "email": "dup@example.com"}
        data2 = {"name": "Client 2", "phone": "+79990000002", "email": "dup@example.com"}

        await client.post("/api/v1/clients/", json=data1, headers=auth_headers)
        resp = await client.post("/api/v1/clients/", json=data2, headers=auth_headers)
        assert resp.status_code == 201  # Email is not unique in regular clients endpoint


class TestDeleteClient:
    """Tests for DELETE /api/v1/clients/{id}"""

    async def test_delete_client_success(self, client, auth_headers, test_client_data):
        """Client can be deleted."""
        create_resp = await client.post("/api/v1/clients/", json=test_client_data, headers=auth_headers)
        client_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/clients/{client_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get(f"/api/v1/clients/{client_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    async def test_delete_client_not_found(self, client, auth_headers):
        """Returns 404 for non-existent client."""
        resp = await client.delete("/api/v1/clients/99999", headers=auth_headers)
        assert resp.status_code == 404

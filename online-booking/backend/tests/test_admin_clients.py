"""Tests for admin clients CRUD endpoints."""
import pytest


class TestAdminGetClients:
    """Tests for GET /api/v1/admin/clients"""

    async def test_get_admin_clients_empty(self, client, auth_headers):
        """Returns empty list when no clients."""
        resp = await client.get("/api/v1/admin/clients", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_admin_clients_with_data(self, client, auth_headers, test_client_data):
        """Returns list of clients."""
        await client.post("/api/v1/admin/clients", json=test_client_data, headers=auth_headers)

        resp = await client.get("/api/v1/admin/clients", headers=auth_headers)
        assert resp.status_code == 200
        clients = resp.json()
        assert len(clients) >= 1
        # Phone is normalized
        assert any("+7" in c["phone"] and "999" in c["phone"] for c in clients)


class TestAdminCreateClient:
    """Tests for POST /api/v1/admin/clients"""

    async def test_admin_create_client(self, client, auth_headers, test_client_data):
        """Admin can create a client."""
        resp = await client.post("/api/v1/admin/clients", json=test_client_data, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == test_client_data["name"]
        assert "+7" in data["phone"] and "999" in data["phone"]

    async def test_admin_create_client_duplicate_phone(self, client, auth_headers, test_client_data):
        """Cannot create client with duplicate phone."""
        await client.post("/api/v1/admin/clients", json=test_client_data, headers=auth_headers)

        resp = await client.post("/api/v1/admin/clients", json=test_client_data, headers=auth_headers)
        assert resp.status_code == 400

    async def test_admin_create_client_duplicate_email(self, client, auth_headers):
        """Cannot create client with duplicate email."""
        data1 = {"name": "Client 1", "phone": "+79990000001", "email": "dup@test.com"}
        data2 = {"name": "Client 2", "phone": "+79990000002", "email": "dup@test.com"}

        await client.post("/api/v1/admin/clients", json=data1, headers=auth_headers)
        resp = await client.post("/api/v1/admin/clients", json=data2, headers=auth_headers)
        assert resp.status_code == 400

    async def test_admin_create_client_no_email(self, client, auth_headers):
        """Can create client without email."""
        resp = await client.post("/api/v1/admin/clients", json={
            "name": "No Email",
            "phone": "+79992220002",
        }, headers=auth_headers)
        assert resp.status_code == 201


class TestAdminUpdateClient:
    """Tests for PATCH /api/v1/admin/clients/{id}"""

    async def test_update_client(self, client, auth_headers, test_client_data):
        """Admin can update a client."""
        create_resp = await client.post(
            "/api/v1/admin/clients", json=test_client_data, headers=auth_headers
        )
        client_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/admin/clients/{client_id}",
            json={"name": "Updated Name", "email": "updated@test.com"},
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert resp.json()["email"] == "updated@test.com"

    async def test_update_client_duplicate_phone(self, client, auth_headers):
        """Cannot update client to duplicate phone."""
        c1 = await client.post("/api/v1/admin/clients", json={
            "name": "C1", "phone": "+79993330003"
        }, headers=auth_headers)
        c2 = await client.post("/api/v1/admin/clients", json={
            "name": "C2", "phone": "+79993330004"
        }, headers=auth_headers)

        resp = await client.patch(
            f"/api/v1/admin/clients/{c2.json()['id']}",
            json={"phone": "+79993330003"},
            headers=auth_headers
        )
        assert resp.status_code == 400

    async def test_update_client_not_found(self, client, auth_headers):
        """Returns 404 for non-existent client."""
        resp = await client.patch(
            "/api/v1/admin/clients/99999",
            json={"name": "Ghost"},
            headers=auth_headers
        )
        assert resp.status_code == 404


class TestAdminDeleteClient:
    """Tests for DELETE /api/v1/admin/clients/{id}"""

    async def test_delete_admin_client(self, client, auth_context, test_client_data):
        """Admin can delete a client."""
        headers = auth_context["headers"]

        client_resp = await client.post(
            "/api/v1/admin/clients", json=test_client_data, headers=headers
        )
        client_id = client_resp.json()["id"]

        resp = await client.delete(f"/api/v1/admin/clients/{client_id}", headers=headers)
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get("/api/v1/admin/clients", headers=headers)
        assert not any(c["id"] == client_id for c in get_resp.json())

    async def test_delete_admin_client_not_found(self, client, auth_headers):
        """Returns 404 for non-existent client."""
        resp = await client.delete("/api/v1/admin/clients/99999", headers=auth_headers)
        assert resp.status_code == 404

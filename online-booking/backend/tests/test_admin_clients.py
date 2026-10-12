"""Tests for admin clients CRUD endpoints."""
import pytest


class TestAdminGetClients:
    """Tests for GET /api/v1/admin/clients"""

    async def test_get_admin_clients_empty(self, client, auth_headers):
        """Returns empty list when no clients."""
        resp = await client.get("/api/v1/admin/clients", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_get_admin_clients_with_data(self, client, auth_headers, test_client_data):
        """Returns list of clients."""
        await client.post("/api/v1/admin/clients", json=test_client_data, headers=auth_headers)

        resp = await client.get("/api/v1/admin/clients", headers=auth_headers)
        assert resp.status_code == 200
        clients = resp.json()["items"]
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

    async def test_delete_admin_client(self, client, auth_headers, test_client_data):
        """Admin can delete a client."""
        headers = auth_headers

        client_resp = await client.post(
            "/api/v1/admin/clients", json=test_client_data, headers=headers
        )
        client_id = client_resp.json()["id"]

        resp = await client.delete(f"/api/v1/admin/clients/{client_id}", headers=headers)
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get("/api/v1/admin/clients", headers=headers)
        assert not any(c["id"] == client_id for c in get_resp.json()["items"])

    async def test_delete_admin_client_not_found(self, client, auth_headers):
        """Returns 404 for non-existent client."""
        resp = await client.delete("/api/v1/admin/clients/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestMasterOwnScope:
    """Masters see strictly their own clients (booked or created by them)."""

    async def _second_master_headers(self, client):
        reg = await client.post("/api/v1/auth/register", json={
            "name": "Second Master", "email": "second_master@example.com",
            "password": "SecurePass123!", "phone": "+79990009988",
            "role": "MASTER",
        })
        assert reg.status_code == 201, reg.text
        login = await client.post("/api/v1/auth/login", json={
            "email": "second_master@example.com", "password": "SecurePass123!"})
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    async def test_master_sees_only_own(self, client, auth_headers):
        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Own Client", "phone": "+79991110011"},
            headers=auth_headers,
        )
        assert created.status_code == 201, created.text

        other = await self._second_master_headers(client)
        resp = await client.get("/api/v1/admin/clients", headers=other)
        assert resp.status_code == 200
        assert resp.json()["items"] == []
        assert resp.json()["total"] == 0

        mine = await client.get("/api/v1/admin/clients", headers=auth_headers)
        assert mine.status_code == 200
        assert any(c["id"] == created.json()["id"] for c in mine.json()["items"])

    async def test_master_cannot_touch_foreign_client(self, client, auth_headers):
        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Foreign", "phone": "+79991110022"},
            headers=auth_headers,
        )
        cid = created.json()["id"]
        other = await self._second_master_headers(client)

        assert (await client.patch(
            f"/api/v1/admin/clients/{cid}", json={"name": "Hacked"}, headers=other,
        )).status_code == 404
        assert (await client.delete(
            f"/api/v1/admin/clients/{cid}", headers=other,
        )).status_code == 404
        assert (await client.post(
            f"/api/v1/admin/clients/{cid}/toggle-active", headers=other,
        )).status_code == 404


class TestClientAddress:
    """Address + city parsed from it (single-field location UX)."""

    async def test_create_with_address_and_city_name(self, client, session, auth_headers):
        from sqlalchemy import select
        from app.models.city import City
        from app.models.country import Country

        country = Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7")
        session.add(country)
        await session.flush()
        session.add(City(country_id=country.id, name_ru="Уфа", name_en="Ufa", slug="ufa"))
        await session.commit()

        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Addr", "phone": "+79991112299",
                  "address": "г. Уфа, ул. Ленина, 5", "city_name": "Уфа"},
            headers=auth_headers,
        )
        assert created.status_code == 201, created.text
        body = created.json()
        assert body["address"] == "г. Уфа, ул. Ленина, 5"
        assert body["city_name"] == "Уфа"
        assert body["city_id"] is not None

        listed = await client.get("/api/v1/admin/clients", headers=auth_headers)
        row = next(c for c in listed.json()["items"] if c["id"] == body["id"])
        assert row["address"] == "г. Уфа, ул. Ленина, 5"

    async def test_update_address(self, client, auth_headers, test_client_data):
        created = await client.post(
            "/api/v1/admin/clients", json=test_client_data, headers=auth_headers
        )
        cid = created.json()["id"]
        r = await client.patch(
            f"/api/v1/admin/clients/{cid}",
            json={"address": "г. Казань, ул. Баумана, 1"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["address"] == "г. Казань, ул. Баумана, 1"

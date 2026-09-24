"""Tests for services CRUD endpoints."""
import pytest


class TestGetServices:
    """Tests for GET /api/v1/services/"""

    async def test_get_services_empty(self, client):
        """Returns empty list when no services."""
        resp = await client.get("/api/v1/services/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_services_with_data(self, client, test_master_data, test_service_data):
        """Returns list of services."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1})

        resp = await client.get("/api/v1/services/")
        assert resp.status_code == 200
        services = resp.json()
        assert len(services) >= 1
        assert services[0]["name"] == test_service_data["name"]


class TestGetServiceById:
    """Tests for GET /api/v1/services/{id}"""

    async def test_get_service_by_id(self, client, test_master_data, test_service_data):
        """Returns service by ID."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        create_resp = await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1})
        service_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/services/{service_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == service_id

    async def test_get_service_not_found(self, client):
        """Returns 404 for non-existent service."""
        resp = await client.get("/api/v1/services/99999")
        assert resp.status_code == 404


class TestCreateService:
    """Tests for POST /api/v1/services/"""

    async def test_create_service_success(self, client, test_master_data, test_service_data):
        """Service can be created."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == test_service_data["name"]
        assert float(data["price"]) == test_service_data["price"]
        assert data["duration_minutes"] == test_service_data["duration_minutes"]
        assert "id" in data

    async def test_create_service_missing_master_id(self, client, test_master_data):
        """Returns 422 when master_id is missing."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.post("/api/v1/services/", json={
            "name": "Test",
            "duration_minutes": 30,
            "price": 1000
        })
        assert resp.status_code == 422


class TestDeleteService:
    """Tests for DELETE /api/v1/services/{id}"""

    async def test_delete_service(self, client, test_master_data, test_service_data):
        """Service can be hard-deleted."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        create_resp = await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1})
        service_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/services/{service_id}")
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get(f"/api/v1/services/{service_id}")
        assert get_resp.status_code == 404

    async def test_delete_service_not_found(self, client):
        """Returns 404 for non-existent service."""
        resp = await client.delete("/api/v1/services/99999")
        assert resp.status_code == 404

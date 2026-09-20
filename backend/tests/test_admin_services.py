"""Tests for admin services CRUD endpoints."""
import pytest


class TestAdminGetServices:
    """Tests for GET /api/v1/admin/services"""

    async def test_get_admin_services_empty(self, client, auth_headers):
        """Returns empty list when no services."""
        resp = await client.get("/api/v1/admin/services", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_admin_services_active_only(self, client, auth_headers, test_master_data, test_service_data):
        """Returns only active services."""
        # Create two services
        await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers)
        await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1, "name": "Service 2"}, headers=auth_headers)

        resp = await client.get("/api/v1/admin/services", headers=auth_headers)
        assert resp.status_code == 200
        services = resp.json()
        assert len(services) >= 2
        # All returned should be active
        assert all(s.get("is_active", True) for s in services)

    async def test_get_all_services_includes_inactive(self, client, auth_headers, test_master_data, test_service_data):
        """GET /services/all returns inactive services too."""
        await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers)

        resp = await client.get("/api/v1/admin/services/all", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestAdminCreateService:
    """Tests for POST /api/v1/admin/services"""

    async def test_admin_create_service(self, client, auth_headers, test_service_data):
        """Admin can create a service."""
        resp = await client.post("/api/v1/admin/services", json={**test_service_data, "master_id": 1}, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json().get("is_active", True) is True

    async def test_admin_create_service_missing_fields(self, client, auth_headers):
        """Returns 422 when required fields are missing."""
        resp = await client.post("/api/v1/admin/services", json={"name": "Test"}, headers=auth_headers)
        assert resp.status_code == 422


class TestAdminUpdateService:
    """Tests for PATCH /api/v1/admin/services/{id}"""

    async def test_update_service(self, client, auth_headers, test_service_data):
        """Admin can update a service."""
        create_resp = await client.post(
            "/api/v1/admin/services",
            json={**test_service_data, "master_id": 1},
            headers=auth_headers
        )
        service_id = create_resp.json()["id"]

        resp = await client.patch(
            f"/api/v1/admin/services/{service_id}",
            json={"name": "Updated Name", "price": 3000},
            headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"
        assert float(resp.json()["price"]) == 3000.0

    async def test_update_service_not_found(self, client, auth_headers):
        """Returns 404 for non-existent service."""
        resp = await client.patch(
            "/api/v1/admin/services/99999",
            json={"name": "Ghost"},
            headers=auth_headers
        )
        assert resp.status_code == 404


class TestAdminDeleteService:
    """Tests for DELETE /api/v1/admin/services/{id}"""

    async def test_admin_soft_delete_service(self, client, auth_headers, test_master_data, test_service_data):
        """Admin soft-deletes a service (is_active=False)."""
        await client.post("/api/v1/auth/register", json=test_master_data)

        create_resp = await client.post(
            "/api/v1/admin/services",
            json={**test_service_data, "master_id": 1},
            headers=auth_headers
        )
        service_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/v1/admin/services/{service_id}", headers=auth_headers)
        assert resp.status_code == 204

        # Verify soft-deleted
        all_resp = await client.get("/api/v1/admin/services/all", headers=auth_headers)
        deleted = [s for s in all_resp.json() if s["id"] == service_id]
        assert len(deleted) == 1
        assert deleted[0]["is_active"] is False

        # Verify not in active list
        active_resp = await client.get("/api/v1/admin/services", headers=auth_headers)
        assert not any(s["id"] == service_id for s in active_resp.json())

    async def test_admin_delete_service_not_found(self, client, auth_headers):
        """Returns 404 for non-existent service."""
        resp = await client.delete("/api/v1/admin/services/99999", headers=auth_headers)
        assert resp.status_code == 404

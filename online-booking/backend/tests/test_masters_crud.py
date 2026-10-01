"""Tests for admin/masters CRUD endpoints.

Covers:
- GET /api/v1/admin/masters — list + search + pagination
- GET /api/v1/admin/masters/{id} — get by ID
- POST /api/v1/admin/masters/ — create master
- PATCH /api/v1/admin/masters/{id} — partial update
- DELETE /api/v1/admin/masters/{id} — delete master
"""
import pytest


# ─── GET /api/v1/admin/masters ──────────────────────────────────────


class TestGetMasters:
    """Tests for GET /api/v1/admin/masters"""

    async def test_list_masters_empty(self, client, super_admin_headers):
        """Returns empty list when no masters exist."""
        resp = await client.get("/api/v1/admin/masters", headers=super_admin_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_masters_with_data(self, client, super_admin_headers, test_master_data):
        """Returns list of masters after registration."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.get("/api/v1/admin/masters", headers=super_admin_headers)
        assert resp.status_code == 200
        masters = resp.json()
        assert len(masters) >= 1
        assert "id" in masters[0]
        assert "name" in masters[0]
        assert "email" in masters[0]

    async def test_list_masters_search_by_name(self, client, super_admin_headers, test_master_data):
        """Search by name returns matching masters."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.get(
            "/api/v1/admin/masters?search=Test+Master",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        masters = resp.json()
        assert len(masters) >= 1
        assert any("Test Master" in m["name"] for m in masters)

    async def test_list_masters_search_by_email(self, client, super_admin_headers, test_master_data):
        """Search by email returns matching masters."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.get(
            "/api/v1/admin/masters?search=test_master@example.com",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        masters = resp.json()
        assert len(masters) >= 1
        assert any("test_master@example.com" in m["email"] for m in masters)

    async def test_list_masters_pagination(self, client, super_admin_headers):
        """Pagination with limit and offset works."""
        resp = await client.get(
            "/api/v1/admin/masters?limit=10&offset=0",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        masters = resp.json()
        assert isinstance(masters, list)
        assert len(masters) <= 10

    async def test_list_masters_invalid_page(self, client, super_admin_headers):
        """Invalid pagination params are handled."""
        resp = await client.get(
            "/api/v1/admin/masters?offset=-1",
            headers=super_admin_headers
        )
        assert resp.status_code == 422

    async def test_list_masters_filter_active(self, client, super_admin_headers, test_master_data):
        """Filter by active status works."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.get(
            "/api/v1/admin/masters?is_active=true",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        masters = resp.json()
        assert isinstance(masters, list)

    async def test_list_masters_filter_admin(self, client, super_admin_headers, test_master_data):
        """Filter by admin status works."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.get(
            "/api/v1/admin/masters?is_admin=true",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        masters = resp.json()
        assert isinstance(masters, list)


# ─── GET /api/v1/admin/masters/{id} ─────────────────────────────────


class TestGetMasterById:
    """Tests for GET /api/v1/admin/masters/{id}"""

    async def test_get_master_by_id(self, client, super_admin_headers, created_master_id):
        """Returns master by ID."""
        resp = await client.get(
            f"/api/v1/admin/masters/{created_master_id}",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created_master_id
        assert "name" in data
        assert "email" in data

    async def test_get_master_not_found(self, client, super_admin_headers):
        """Returns 404 for non-existent master."""
        resp = await client.get(
            "/api/v1/admin/masters/99999",
            headers=super_admin_headers
        )
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower() or "найден" in resp.json()["detail"]


# ─── POST /api/v1/admin/masters/ ────────────────────────────────────


class TestCreateMaster:
    """Tests for POST /api/v1/admin/masters/"""

    async def test_create_master(self, client, super_admin_headers):
        """Master can be created via admin endpoint."""
        data = {
            "name": "New Master via Admin API",
            "email": "new_master_admin@example.com",
            "password": "TestPass123!",
            "phone": "+79991112233",
            "telegram_username": "new_master_admin"
        }
        resp = await client.post(
            "/api/v1/admin/masters",
            json=data,
            headers=super_admin_headers
        )
        assert resp.status_code == 201
        created = resp.json()
        assert created["name"] == data["name"]
        assert created["email"] == data["email"]
        assert "id" in created

    async def test_create_master_duplicate_email(self, client, super_admin_headers):
        """Cannot create master with duplicate email."""
        data = {
            "name": "First Master",
            "email": "dup_admin@example.com",
            "password": "TestPass123!",
            "phone": "+79990000011"
        }
        await client.post(
            "/api/v1/admin/masters",
            json=data,
            headers=super_admin_headers
        )
        resp = await client.post(
            "/api/v1/admin/masters",
            json=data,
            headers=super_admin_headers
        )
        assert resp.status_code == 400
        assert "уже существует" in resp.json()["detail"]

    async def test_create_master_duplicate_phone(self, client, super_admin_headers):
        """Cannot create master with duplicate phone."""
        data = {
            "name": "First Master",
            "email": "dup_phone1@example.com",
            "password": "TestPass123!",
            "phone": "+79990000012"
        }
        await client.post(
            "/api/v1/admin/masters",
            json=data,
            headers=super_admin_headers
        )
        resp = await client.post(
            "/api/v1/admin/masters",
            json={
                "name": "Second Master",
                "email": "dup_phone2@example.com",
                "password": "TestPass123!",
                "phone": "+79990000012"
            },
            headers=super_admin_headers
        )
        assert resp.status_code == 400
        assert "уже существует" in resp.json()["detail"]


# ─── PATCH /api/v1/admin/masters/{id} ───────────────────────────────


class TestUpdateMaster:
    """Tests for PATCH /api/v1/admin/masters/{id}"""

    async def test_update_master(self, client, super_admin_headers, created_master_id):
        """Master can be fully updated."""
        resp = await client.patch(
            f"/api/v1/admin/masters/{created_master_id}",
            json={
                "name": "Updated Master Name",
                "phone": "+79990001133",
                "telegram_username": "updated_master"
            },
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Master Name"
        assert data["phone"] == "+79990001133"

    async def test_update_master_partial(self, client, super_admin_headers, created_master_id):
        """Only specified fields are updated (partial update)."""
        resp = await client.patch(
            f"/api/v1/admin/masters/{created_master_id}",
            json={"name": "Partially Updated"},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Partially Updated"
        assert data["email"] == "test_master@example.com"

    async def test_update_master_invalid_data(self, client, super_admin_headers, created_master_id):
        """Update with invalid data returns 422."""
        resp = await client.patch(
            f"/api/v1/admin/masters/{created_master_id}",
            json={"password": "weak"},
            headers=super_admin_headers
        )
        assert resp.status_code == 422

    async def test_update_master_not_found(self, client, super_admin_headers):
        """Returns 404 when updating non-existent master."""
        resp = await client.patch(
            "/api/v1/admin/masters/99999",
            json={"name": "Ghost"},
            headers=super_admin_headers
        )
        assert resp.status_code == 404


# ─── DELETE /api/v1/admin/masters/{id} ──────────────────────────────


class TestDeleteMaster:
    """Tests for DELETE /api/v1/admin/masters/{id}"""

    async def test_delete_master(self, client, super_admin_headers, created_master_id):
        """Master can be deleted."""
        resp = await client.delete(
            f"/api/v1/admin/masters/{created_master_id}",
            headers=super_admin_headers
        )
        assert resp.status_code == 200

        get_resp = await client.get(
            f"/api/v1/admin/masters/{created_master_id}",
            headers=super_admin_headers
        )
        assert get_resp.status_code == 404

    async def test_delete_master_not_found(self, client, super_admin_headers):
        """Returns 404 when deleting non-existent master."""
        resp = await client.delete(
            "/api/v1/admin/masters/99999",
            headers=super_admin_headers
        )
        assert resp.status_code == 404

"""Tests for masters CRUD endpoints."""
import pytest


class TestGetMasters:
    """Tests for GET /api/v1/masters/"""

    async def test_get_masters_empty(self, client):
        """Returns empty list when no masters exist."""
        resp = await client.get("/api/v1/masters/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_masters_with_data(self, client, test_master_data):
        """Returns list of masters."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        resp = await client.get("/api/v1/masters/")
        assert resp.status_code == 200
        masters = resp.json()
        assert len(masters) >= 1
        assert "id" in masters[0]
        assert "name" in masters[0]
        assert "email" in masters[0]


class TestGetMasterById:
    """Tests for GET /api/v1/masters/{id}"""

    async def test_get_master_by_id(self, client, test_master_data):
        """Returns master by ID."""
        # Register and get ID
        reg_resp = await client.post("/api/v1/auth/register", json=test_master_data)
        master_id = reg_resp.json()["id"]

        resp = await client.get(f"/api/v1/masters/{master_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == master_id

    async def test_get_master_not_found(self, client):
        """Returns 404 for non-existent master."""
        resp = await client.get("/api/v1/masters/99999")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestCreateMaster:
    """Tests for POST /api/v1/masters/"""

    async def test_create_master(self, client):
        """Master can be created via masters endpoint."""
        data = {
            "name": "New Master via API",
            "email": "new_master_api@example.com",
            "password": "TestPass123!",
            "phone": "+79991112233",
            "telegram_username": "new_master_api",
            "description": "Test description"
        }
        resp = await client.post("/api/v1/masters/", json=data)
        assert resp.status_code == 201
        created = resp.json()
        assert created["name"] == data["name"]
        assert created["email"] == data["email"]
        assert "id" in created

    async def test_create_master_duplicate_email(self, client):
        """Cannot create master with duplicate email."""
        data = {
            "name": "First",
            "email": "dup_masters@example.com",
            "password": "TestPass123!",
            "phone": "+79990000001",
            "telegram_username": "first"
        }
        await client.post("/api/v1/masters/", json=data)

        resp = await client.post("/api/v1/masters/", json=data)
        assert resp.status_code == 400


class TestUpdateMaster:
    """Tests for PATCH /api/v1/masters/{id}"""

    async def test_update_master(self, client):
        """Master can be updated."""
        # Create master first
        create_resp = await client.post("/api/v1/masters/", json={
            "name": "Original Name",
            "email": "update_test@example.com",
            "password": "TestPass123!",
            "phone": "+79990000002",
            "telegram_username": "original"
        })
        master_id = create_resp.json()["id"]

        # Update
        resp = await client.patch(f"/api/v1/masters/{master_id}", json={
            "name": "Updated Master Name",
            "phone": "+79990001133",
            "telegram_username": "updated_master"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Updated Master Name"
        assert data["phone"] == "+79990001133"

    async def test_update_master_not_found(self, client):
        """Returns 404 when updating non-existent master."""
        resp = await client.patch("/api/v1/masters/99999", json={"name": "Ghost"})
        assert resp.status_code == 404


class TestDeleteMaster:
    """Tests for DELETE /api/v1/masters/{id}"""

    async def test_delete_master(self, client):
        """Master can be deleted."""
        # Create master
        create_resp = await client.post("/api/v1/masters/", json={
            "name": "To Be Deleted",
            "email": "delete_test@example.com",
            "password": "TestPass123!",
            "phone": "+79990000003",
            "telegram_username": "delete_me"
        })
        master_id = create_resp.json()["id"]

        # Delete
        resp = await client.delete(f"/api/v1/masters/{master_id}")
        assert resp.status_code == 200

        # Verify deleted
        get_resp = await client.get(f"/api/v1/masters/{master_id}")
        assert get_resp.status_code == 404

    async def test_delete_master_not_found(self, client):
        """Returns 404 when deleting non-existent master."""
        resp = await client.delete("/api/v1/masters/99999")
        assert resp.status_code == 404

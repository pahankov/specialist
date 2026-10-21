"""Tests for admin services CRUD endpoints."""
import pytest


class TestAdminGetServices:
    """Tests for GET /api/v1/admin/services"""

    async def test_get_admin_services_empty(self, client, auth_headers):
        """Returns empty list when no services."""
        resp = await client.get("/api/v1/admin/services", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    async def test_get_admin_services_active_only(self, client, auth_headers, test_master_data, test_service_data):
        """Returns only active services."""
        # Create two services
        await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers)
        await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1, "name": "Service 2"}, headers=auth_headers)

        resp = await client.get("/api/v1/admin/services", headers=auth_headers)
        assert resp.status_code == 200
        services = resp.json()["items"]
        assert len(services) >= 2
        # All returned should be active
        assert all(s.get("is_active", True) for s in services)

    async def test_get_all_services_includes_inactive(self, client, auth_headers, test_master_data, test_service_data):
        """GET /services/all returns inactive services too."""
        await client.post("/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=auth_headers)

        resp = await client.get("/api/v1/admin/services/all", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    async def test_services_sort_by_price(self, client, auth_headers, test_master_data, test_service_data):
        """sort_by=price&sort_dir=desc returns most expensive first."""
        for name, price in (("Cheap", 500), ("Mid", 1500), ("Top", 3000)):
            await client.post(
                "/api/v1/services/",
                json={**test_service_data, "master_id": 1, "name": name, "price": price},
                headers=auth_headers,
            )

        resp = await client.get(
            "/api/v1/admin/services",
            params={"sort_by": "price", "sort_dir": "desc"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        prices = [float(i["price"]) for i in resp.json()["items"]]
        assert prices == sorted(prices, reverse=True)

    async def test_services_sort_by_duration(self, client, auth_headers, test_master_data, test_service_data):
        """sort_by=duration orders by minutes ascending."""
        for name, mins in (("Long", 120), ("Short", 30), ("Mid", 60)):
            await client.post(
                "/api/v1/services/",
                json={**test_service_data, "master_id": 1, "name": name,
                      "duration_minutes": mins},
                headers=auth_headers,
            )

        resp = await client.get(
            "/api/v1/admin/services",
            params={"sort_by": "duration", "sort_dir": "asc"},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        got = [i["duration_minutes"] for i in resp.json()["items"]]
        assert got == sorted(got)


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
        deleted = [s for s in all_resp.json()["items"] if s["id"] == service_id]
        assert len(deleted) == 1
        assert deleted[0]["is_active"] is False

        # Verify not in active list
        active_resp = await client.get("/api/v1/admin/services", headers=auth_headers)
        assert not any(s["id"] == service_id for s in active_resp.json()["items"])

    async def test_admin_delete_service_not_found(self, client, auth_headers):
        """Returns 404 for non-existent service."""
        resp = await client.delete("/api/v1/admin/services/99999", headers=auth_headers)
        assert resp.status_code == 404


class TestAdminServiceAuditUserId:
    """Regression: audit_logs.master_id FK points to users.id.

    Production has master User.id=302 and MasterProfile.id=91. Passing the
    profile id to log_action made every service create/update/delete a 500.
    """

    async def test_service_audit_uses_user_id_not_profile_id(
        self, client, session, test_master_data, test_service_data
    ):
        from sqlalchemy import select

        from app.models.audit_log import AuditLog
        from app.models.master_profile import MasterProfile
        from app.models.user import User, UserRole
        from app.modules.auth.token import create_access_token

        # Consume user id 1 so the registered master's user id differs from
        # their master_profile id (the production-shaped mismatch).
        session.add(User(
            name="Seed User",
            email="seed_audit@example.com",
            role=UserRole.CLIENT,
        ))
        await session.commit()

        reg = await client.post("/api/v1/auth/register", json=test_master_data)
        assert reg.status_code == 201, reg.text
        user = (await session.execute(
            select(User).where(User.email == test_master_data["email"])
        )).scalar_one()
        profile = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        assert profile.id != user.id

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "last_name": user.last_name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        created = await client.post(
            "/api/v1/admin/services", json=test_service_data, headers=headers
        )
        assert created.status_code == 201, created.text
        service_id = created.json()["id"]
        assert created.json()["master_id"] == profile.id

        updated = await client.patch(
            f"/api/v1/admin/services/{service_id}",
            json={"name": "Audit FK check"},
            headers=headers,
        )
        assert updated.status_code == 200, updated.text

        deleted = await client.delete(
            f"/api/v1/admin/services/{service_id}", headers=headers
        )
        assert deleted.status_code == 204, deleted.text

        logs = (await session.execute(
            select(AuditLog).where(
                AuditLog.entity_type == "service",
                AuditLog.entity_id == service_id,
            )
        )).scalars().all()
        assert len(logs) == 3
        assert {log.master_id for log in logs} == {user.id}

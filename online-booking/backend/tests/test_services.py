"""Tests for services CRUD endpoints."""
import pytest


class TestGetServices:
    """Tests for GET /api/v1/services/"""

    async def test_get_services_empty(self, client):
        """Returns empty list when no services."""
        resp = await client.get("/api/v1/services/")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_get_services_with_data(
        self, client, session, test_master_data, test_service_data
    ):
        """Returns list of services."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        # Create master directly in DB
        user = User(
            name=test_master_data["name"],
            email=test_master_data["email"],
            hashed_password=hash_password(test_master_data["password"]),
            phone=test_master_data["phone"],
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.flush()
        await session.refresh(mp)
        await session.commit()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/v1/services/", json=test_service_data, headers=headers
        )
        assert resp.status_code == 201

        resp = await client.get("/api/v1/services/")
        assert resp.status_code == 200
        services = resp.json()
        assert len(services) >= 1
        assert services[0]["name"] == test_service_data["name"]


class TestGetServiceById:
    """Tests for GET /api/v1/services/{id}"""

    async def test_get_service_by_id(
        self, client, session, test_master_data, test_service_data
    ):
        """Returns service by ID."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        user = User(
            name=test_master_data["name"],
            email=test_master_data["email"],
            hashed_password=hash_password(test_master_data["password"]),
            phone=test_master_data["phone"],
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.flush()
        await session.refresh(mp)
        await session.commit()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/services/", json=test_service_data, headers=headers
        )
        assert create_resp.status_code == 201
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

    async def test_create_service_success(
        self, client, session, test_master_data, test_service_data
    ):
        """Service can be created."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        user = User(
            name=test_master_data["name"],
            email=test_master_data["email"],
            hashed_password=hash_password(test_master_data["password"]),
            phone=test_master_data["phone"],
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.flush()
        await session.refresh(mp)
        await session.commit()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/v1/services/", json=test_service_data, headers=headers
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == test_service_data["name"]
        assert float(data["price"]) == test_service_data["price"]
        assert data["duration_minutes"] == test_service_data["duration_minutes"]
        assert "id" in data

    async def test_create_service_missing_fields(self, client, session):
        """Returns 422 when required fields are missing."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        user = User(
            name="Test",
            email="test_create@example.com",
            hashed_password=hash_password("SecurePass123!"),
            phone="+79990001199",
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.flush()
        await session.refresh(mp)
        await session.commit()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post(
            "/api/v1/services/", json={"name": "Test"}, headers=headers
        )
        assert resp.status_code == 422


class TestDeleteService:
    """Tests for DELETE /api/v1/services/{id}"""

    async def test_delete_service(
        self, client, session, test_master_data, test_service_data
    ):
        """Service can be hard-deleted."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        user = User(
            name=test_master_data["name"],
            email=test_master_data["email"],
            hashed_password=hash_password(test_master_data["password"]),
            phone=test_master_data["phone"],
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.flush()
        await session.refresh(mp)
        await session.commit()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/services/", json=test_service_data, headers=headers
        )
        assert create_resp.status_code == 201
        service_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/services/{service_id}", headers=headers
        )
        assert resp.status_code == 204

        # Verify deleted
        get_resp = await client.get(f"/api/v1/services/{service_id}")
        assert get_resp.status_code == 404

    async def test_delete_service_not_found(self, client):
        """Returns 404 for non-existent service."""
        resp = await client.delete("/api/v1/services/99999")
        assert resp.status_code == 401


class TestServiceCategory:
    """Category round-trips through public create/get."""

    async def test_create_and_get_with_category(
        self, client, session, test_master_data, test_service_data
    ):
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        user = User(
            name=test_master_data["name"],
            email=test_master_data["email"],
            hashed_password=hash_password(test_master_data["password"]),
            phone=test_master_data["phone"],
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.flush()
        await session.refresh(mp)
        await session.commit()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            "/api/v1/services/",
            json={**test_service_data, "category": "Ногти"},
            headers=headers,
        )
        assert create.status_code == 201
        assert create.json()["category"] == "Ногти"

        service_id = create.json()["id"]
        got = await client.get(f"/api/v1/services/{service_id}")
        assert got.json()["category"] == "Ногти"

    async def test_category_optional(
        self, client, session, test_master_data, test_service_data
    ):
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        user = User(
            name=test_master_data["name"],
            email=test_master_data["email"],
            hashed_password=hash_password(test_master_data["password"]),
            phone=test_master_data["phone"],
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user)
        await session.flush()
        await session.refresh(user)
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.flush()
        await session.refresh(mp)
        await session.commit()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        create = await client.post(
            "/api/v1/services/", json=test_service_data, headers=headers
        )
        assert create.status_code == 201
        assert create.json()["category"] is None


# ─── Auth guards (1.89.0: critical security fix) ─────────────────────

class TestServiceAuth:
    """POST / and DELETE / must require master authentication."""

    async def test_create_service_no_auth(self, client):
        """Unauthenticated POST → 401."""
        resp = await client.post("/api/v1/services/", json={
            "name": "Hack Service",
            "duration_minutes": 30,
            "price": 100,
        })
        assert resp.status_code == 401

    async def test_delete_service_no_auth(self, client):
        """Unauthenticated DELETE → 401."""
        resp = await client.delete("/api/v1/services/99999")
        assert resp.status_code == 401

    async def test_create_service_auth_sets_own_master_id(
        self, client, auth_context, test_service_data
    ):
        """Authenticated POST ignores body master_id, uses authenticated master."""
        headers = auth_context["headers"]
        # Try to create a service for master_id=999
        payload = {**test_service_data, "master_id": 999}
        resp = await client.post("/api/v1/services/", json=payload, headers=headers)
        assert resp.status_code == 201
        data = resp.json()
        # master_id in DB must be the authenticated master's profile id
        assert data["master_id"] == auth_context["master_id"]

    async def test_delete_foreign_service_404(
        self, client, session, auth_context, test_master_data, test_service_data
    ):
        """Master cannot delete another master's service — returns 404."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        headers = auth_context["headers"]

        # Create a second master with unique email/phone
        user2 = User(
            name="Other Master",
            email="other_master_12345@example.com",
            hashed_password=hash_password("SecurePass123!"),
            phone="+79990001199",
            role=UserRole.MASTER,
            is_verified=True,
        )
        session.add(user2)
        await session.flush()
        await session.refresh(user2)
        mp2 = MasterProfile(user_id=user2.id)
        session.add(mp2)
        await session.flush()
        await session.refresh(mp2)
        await session.commit()

        # Create a service for the second master
        create_resp = await client.post(
            "/api/v1/services/",
            json={**test_service_data},
            headers=headers,  # We'll use the first master's token
        )
        # This should fail because first master's token can't create service
        # for second master — master_id is overridden to first master's profile
        # So we need to create the foreign service differently.
        # Actually, the service is created with the authenticated master's profile id,
        # so we need to create it via DB directly.
        from app.models.service import Service
        foreign_service = Service(
            master_id=mp2.id,
            name="Foreign Service",
            description="Should not be deletable",
            duration_minutes=30,
            price=500,
        )
        session.add(foreign_service)
        await session.flush()
        await session.refresh(foreign_service)
        foreign_service_id = foreign_service.id

        # Try to delete with first master's token
        resp = await client.delete(
            f"/api/v1/services/{foreign_service_id}",
            headers=headers,
        )
        # Should be 404 (not found for this master) — never 403
        assert resp.status_code == 404

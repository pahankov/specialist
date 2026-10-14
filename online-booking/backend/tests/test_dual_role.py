"""Tests for dual-role accounts (master acts as client, client upgrades)."""
import pytest


@pytest.fixture
async def master_token(client):
    """Master registered via API, returns access token."""
    reg = await client.post("/api/v1/auth/register", json={
        "name": "Dual Master", "email": "dual_master@example.com",
        "password": "SecurePass123!", "phone": "+79991114444",
        "role": "MASTER",
    })
    assert reg.status_code == 201, reg.text
    login = await client.post("/api/v1/auth/login", json={
        "email": "dual_master@example.com", "password": "SecurePass123!"})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestMasterAsClient:
    async def test_master_opens_client_cabinet(self, client, master_token):
        r = await client.get("/api/v1/client/me", headers=_auth(master_token))
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Dual Master"

    async def test_master_books_as_client(self, client, session, master_token):
        from sqlalchemy import select
        from app.models.service import Service
        from app.models.master_profile import MasterProfile
        from datetime import datetime, timedelta, timezone

        mp_id = (await session.execute(select(MasterProfile.id))).scalars().first()
        svc_id = (await session.execute(
            select(Service.id).where(Service.master_id == mp_id)
        )).scalars().first()
        if svc_id is None:
            svc = Service(master_id=mp_id, name="Cut",
                          duration_minutes=60, price=1000)
            session.add(svc)
            await session.commit()
            svc_id = svc.id
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post("/api/v1/client/appointments",
                              headers=_auth(master_token), json={
                                  "master_id": mp_id, "service_id": svc_id,
                                  "appointment_date": dt,
                              })
        assert r.status_code == 201, r.text

    async def test_admin_still_rejected_from_cabinet(
        self, client, super_admin_headers,
    ):
        r = await client.get("/api/v1/client/me", headers=super_admin_headers)
        assert r.status_code == 401


class TestBecomeMaster:
    async def _register_client(self, client):
        r = await client.post("/api/v1/auth/register-unified", json={
            "name": "Soon Master", "email": "soon_master@example.com",
            "phone": "+79991115555", "password": "SecurePass123!",
            "is_master": False,
        })
        assert r.status_code == 201, r.text
        return r.json()["access_token"]

    async def test_upgrade_flow(self, client, session):
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile

        token = await self._register_client(client)
        r = await client.post("/api/v1/auth/become-master",
                              headers=_auth(token))
        assert r.status_code == 200, r.text
        assert "access_token" in r.json()

        user = (await session.execute(
            select(User).where(User.email == "soon_master@example.com")
        )).scalar_one()
        assert user.role == UserRole.MASTER
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one_or_none()
        assert mp is not None

        # New master token opens the master panel…
        new_token = r.json()["access_token"]
        r = await client.get("/api/v1/admin/profile",
                             headers=_auth(new_token))
        assert r.status_code == 200, r.text
        # …and still the client cabinet (dual-role).
        r = await client.get("/api/v1/client/me", headers=_auth(new_token))
        assert r.status_code == 200, r.text

    async def test_double_upgrade_rejected(self, client):
        token = await self._register_client(client)
        assert (await client.post("/api/v1/auth/become-master",
                                  headers=_auth(token))).status_code == 200
        # Same (client-role) token now resolves to a MASTER user in DB.
        r = await client.post("/api/v1/auth/become-master",
                              headers=_auth(token))
        assert r.status_code == 400, r.text

    async def test_unauthorized_rejected(self, client):
        assert (await client.post("/api/v1/auth/become-master")).status_code in (
            401, 403)

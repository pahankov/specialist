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
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        from datetime import datetime, timedelta, timezone

        # A DIFFERENT master to book with (self-booking is 400).
        other = User(name="Other Master", email="other_m@example.com",
                     phone="+7 (999) 111-00-11",
                     hashed_password=hash_password("Password1!"),
                     role=UserRole.MASTER, is_active=True)
        session.add(other)
        await session.flush()
        session.add(MasterProfile(user_id=other.id))
        await session.flush()
        mp_id = (await session.execute(
            select(MasterProfile.id).where(MasterProfile.user_id == other.id)
        )).scalar_one()
        svc = Service(master_id=mp_id, name="Cut",
                      duration_minutes=60, price=1000)
        session.add(svc)
        await session.commit()
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post("/api/v1/client/appointments",
                              headers=_auth(master_token), json={
                                  "master_id": mp_id, "service_id": svc.id,
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


class TestInboxScoping:
    """Dual-role inbox: each cabinet sees only its own side."""

    async def _bell(self, session, sender_id, recipient_id, text):
        from app.models.notification import Notification

        note = Notification(sender_id=sender_id, recipient_id=recipient_id,
                            text=text, audience="booking")
        session.add(note)
        await session.commit()
        return note.id

    async def test_sides_do_not_leak(self, client, session, master_token):
        from sqlalchemy import select
        from app.models.user import User

        me = (await session.execute(
            select(User).where(User.email == "dual_master@example.com")
        )).scalar_one()
        stranger = User(name="Stranger", email="stranger@example.com",
                        phone="+79991116666", role="CLIENT", is_active=True)
        session.add(stranger)
        await session.flush()
        await self._bell(session, stranger.id, me.id, "Новая запись: Stranger")
        await self._bell(session, me.id, me.id, "Служебная себе")
        # Master-sent bell to me-as-client (e.g. block from another master).
        other_master = User(name="Other", email="other@example.com",
                            phone="+79991117777", role="MASTER",
                            is_active=True)
        session.add(other_master)
        await session.commit()
        await self._bell(session, other_master.id, me.id,
                         "Мастер Other ограничил вам запись")

        h = {"Authorization": f"Bearer {master_token}"}
        inbox = (await client.get("/api/v1/client/notifications/inbox",
                                  headers=h)).json()
        texts = [i["text"] for i in inbox["items"]]
        assert any("ограничил вам запись" in t for t in texts), texts
        assert not any("Новая запись: Stranger" in t for t in texts), texts

        panel = (await client.get("/api/v1/admin/notifications/inbox",
                                  headers=h)).json()
        ptexts = [i["text"] for i in panel["items"]]
        assert any("Новая запись: Stranger" in t for t in ptexts), ptexts
        assert not any("ограничил вам запись" in t for t in ptexts), ptexts

    async def test_badges_match_scopes(self, client, session, master_token):
        from sqlalchemy import select
        from app.models.user import User

        me = (await session.execute(
            select(User).where(User.email == "dual_master@example.com")
        )).scalar_one()
        stranger = User(name="Stranger2", email="stranger2@example.com",
                        phone="+79991118888", role="CLIENT", is_active=True)
        session.add(stranger)
        await session.commit()
        await self._bell(session, stranger.id, me.id, "Новая запись: S2")

        h = {"Authorization": f"Bearer {master_token}"}
        cab = await client.get("/api/v1/client/notifications/unread-count",
                               headers=h)
        assert cab.json()["unread"] == 0
        panel = await client.get("/api/v1/admin/notifications/unread-count",
                                 headers=h)
        assert panel.json()["unread"] == 1


class TestNoSelfBooking:
    async def test_cabinet_self_book_400(self, client, session, master_token):
        from sqlalchemy import select
        from app.models.service import Service
        from app.models.master_profile import MasterProfile
        from app.models.user import User
        from datetime import datetime, timedelta, timezone

        me = (await session.execute(
            select(User).where(User.email == "dual_master@example.com")
        )).scalar_one()
        mp_id = (await session.execute(
            select(MasterProfile.id).where(MasterProfile.user_id == me.id)
        )).scalar_one()
        svc = Service(master_id=mp_id, name="Self Cut",
                      duration_minutes=60, price=500)
        session.add(svc)
        await session.commit()
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post(
            "/api/v1/client/appointments",
            headers={"Authorization": f"Bearer {master_token}"}, json={
                "master_id": mp_id, "service_id": svc.id,
                "appointment_date": dt,
            })
        assert r.status_code == 400, r.text

    async def test_public_self_book_400(self, client, session):
        from sqlalchemy import select
        from app.models.service import Service
        from app.models.master_profile import MasterProfile
        from app.models.user import User
        from datetime import datetime, timedelta, timezone

        mu = User(name="Selfy", email="selfy@example.com",
                  phone="+7 (999) 111-99-99", role="MASTER", is_active=True)
        session.add(mu)
        await session.flush()
        session.add(MasterProfile(user_id=mu.id))
        await session.flush()
        # Master with a client profile (dual-role): public lookup finds them.
        from app.models.client_profile import ClientProfile
        session.add(ClientProfile(user_id=mu.id))
        await session.flush()
        mp_id = (await session.execute(
            select(MasterProfile.id).where(MasterProfile.user_id == mu.id)
        )).scalar_one()
        svc = Service(master_id=mp_id, name="Cut",
                      duration_minutes=60, price=500)
        session.add(svc)
        await session.commit()
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post("/api/v1/appointments/public", json={
            "master_id": mp_id, "service_id": svc.id,
            "client_name": "Selfy", "client_phone": "+79991119999",
            "appointment_date": dt,
        })
        assert r.status_code == 400, r.text

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
    """Application (1.82.0): full profile + verified contacts, admin approval."""

    @staticmethod
    def _payload(**over):
        data = {
            "name": "Тест",
            "last_name": "Клиент",
            "cabinet_address": "ул. Тестовая, 1",
        }
        data.update(over)
        return data

    async def _register_client(self, client, phone, email):
        """Create a client with both contacts (email added, not verified yet)."""
        r = await client.post("/api/v1/auth/register-unified", json={
            "phone": phone, "password": "SecurePass123!", "consent": True,
        })
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        add = await client.post(
            "/api/v1/client/contacts",
            headers=_auth(token),
            json={"contact_type": "email", "value": email},
        )
        assert add.status_code in (200, 201), add.text
        return token, add.json()["id"]

    async def _verify_email(self, session, contact_id):
        from app.models.user_contact import UserContact

        contact = await session.get(UserContact, contact_id)
        assert contact is not None
        contact.is_verified = True
        contact.verified_via = "code"
        await session.commit()

    async def test_application_flow(self, client, session):
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile

        token, email_id = await self._register_client(
            client, "+79991115555", "flow@example.com")
        await self._verify_email(session, email_id)

        r = await client.post("/api/v1/auth/become-master",
                              headers=_auth(token),
                              json=self._payload(
                                  description="Бровист",
                                  experience_years=5,
                                  prefer_master_cabinet=False,
                              ))
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pending"

        # Still a client: no panel, invisible publicly.
        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 111-55-55")
        )).scalar_one()
        assert user.role == UserRole.CLIENT
        assert user.name == "Тест Клиент" and user.last_name == "Клиент"
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        assert mp.is_active is False and mp.status == "inactive"
        assert mp.cabinet_address == "ул. Тестовая, 1"
        assert mp.description == "Бровист"
        assert mp.prefer_master_cabinet is False

        status = await client.get("/api/v1/auth/become-master",
                                  headers=_auth(token))
        assert status.status_code == 200, status.text
        body = status.json()
        assert body["status"] == "pending"
        assert body["application"]["cabinet_address"] == "ул. Тестовая, 1"
        assert body["application"]["prefer_master_cabinet"] is False

        pub = await client.get("/api/v1/masters/")
        assert all(m["user_id"] != user.id for m in pub.json())

        panel = await client.get("/api/v1/admin/profile",
                                 headers=_auth(token))
        assert panel.status_code == 401

    async def test_double_apply_rejected(self, client, session):
        token, email_id = await self._register_client(
            client, "+79991115556", "double@example.com")
        await self._verify_email(session, email_id)
        assert (await client.post("/api/v1/auth/become-master",
                                  headers=_auth(token),
                                  json=self._payload())).status_code == 200
        r = await client.post("/api/v1/auth/become-master",
                              headers=_auth(token), json=self._payload())
        assert r.status_code == 400, r.text

    async def test_requires_email(self, client, session):
        token, _ = await self._register_client(
            client, "+79991115557", "no-email@example.com")
        # Remove the email: only a phone is left.
        from sqlalchemy import select
        from app.models.user_contact import UserContact

        contact = (await session.execute(
            select(UserContact).where(UserContact.value == "no-email@example.com")
        )).scalar_one()
        await session.delete(contact)
        await session.commit()

        r = await client.post("/api/v1/auth/become-master",
                              headers=_auth(token), json=self._payload())
        assert r.status_code == 400, r.text
        assert "почт" in r.json()["detail"].lower()

    async def test_requires_verified_contact(self, client, session):
        token, _ = await self._register_client(
            client, "+79991115558", "unverified@example.com")
        # Both contact types exist, but neither is verified.
        r = await client.post("/api/v1/auth/become-master",
                              headers=_auth(token), json=self._payload())
        assert r.status_code == 400, r.text
        assert "подтвердите" in r.json()["detail"].lower()

    async def test_photo_upload_is_optional(self, client, session):
        token, email_id = await self._register_client(
            client, "+79991115559", "photo@example.com")
        await self._verify_email(session, email_id)

        # 1x1 transparent PNG.
        png = bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
            "1f15c4890000000d49444154789c6360000000020001e221bc33000000"
            "0049454e44ae426082"
        )
        up = await client.post(
            "/api/v1/auth/become-master/photo?kind=avatar",
            headers=_auth(token),
            files={"file": ("photo.png", png, "image/png")},
        )
        assert up.status_code == 200, up.text
        url = up.json()["avatar_url"]
        assert url.startswith("/static/avatars/")

        r = await client.post("/api/v1/auth/become-master",
                              headers=_auth(token),
                              json=self._payload(avatar_url=url))
        assert r.status_code == 200, r.text

        from sqlalchemy import select
        from app.models.user import User
        from app.models.master_profile import MasterProfile

        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 111-55-59")
        )).scalar_one()
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        assert mp.avatar_url == url

        # Tests must not litter the repo.
        import os as _os

        _os.remove(_os.path.join(
            "app", "static", "avatars", _os.path.basename(url)))

    async def test_admin_activation_opens_panel(
        self, client, session, super_admin_headers,
    ):
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile

        token, email_id = await self._register_client(
            client, "+79991115560", "activation@example.com")
        await self._verify_email(session, email_id)
        await client.post("/api/v1/auth/become-master",
                          headers=_auth(token), json=self._payload())
        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 111-55-60")
        )).scalar_one()
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()

        # Applications are visible to the superadmin and marked as such.
        default_list = await client.get("/api/v1/admin/masters",
                                        headers=super_admin_headers)
        assert default_list.status_code == 200
        assert all(m["user_id"] != user.id for m in default_list.json())

        admin_list = await client.get(
            "/api/v1/admin/masters?include_applications=true",
            headers=super_admin_headers,
        )
        assert admin_list.status_code == 200, admin_list.text
        pending = next(m for m in admin_list.json() if m["user_id"] == user.id)
        assert pending["is_application"] is True

        r = await client.post(f"/api/v1/admin/masters/{mp.id}/toggle-active",
                              headers=super_admin_headers)
        assert r.status_code == 200, r.text

        await session.refresh(user)
        assert user.role == UserRole.MASTER
        pub = await client.get("/api/v1/masters/")
        assert any(m["user_id"] == user.id for m in pub.json())

        approved = await client.get(
            "/api/v1/admin/masters?include_applications=true",
            headers=super_admin_headers,
        )
        row = next(m for m in approved.json() if m["user_id"] == user.id)
        assert row["is_application"] is False

    async def test_landing_preference_in_login_token(
        self, client, session, super_admin_headers,
    ):
        import jwt
        from sqlalchemy import select
        from app.config import settings
        from app.models.user import User
        from app.models.master_profile import MasterProfile

        token, email_id = await self._register_client(
            client, "+79991115561", "landing@example.com")
        await self._verify_email(session, email_id)
        await client.post("/api/v1/auth/become-master",
                          headers=_auth(token),
                          json=self._payload(prefer_master_cabinet=False))
        user = (await session.execute(
            select(User).where(User.phone == "+7 (999) 111-55-61")
        )).scalar_one()
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        await client.post(f"/api/v1/admin/masters/{mp.id}/toggle-active",
                          headers=super_admin_headers)

        def claim(access: str) -> dict:
            return jwt.decode(access, settings.SECRET_KEY,
                              algorithms=[settings.ALGORITHM])

        login = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "+7 (999) 111-55-61",
            "password": "SecurePass123!",
        })
        assert login.status_code == 200, login.text
        assert claim(login.json()["access_token"])["prefer_master"] is False

        # The master can flip it in the panel profile; the next login sees it.
        upd = await client.patch("/api/v1/admin/profile",
                                 headers=_auth(login.json()["access_token"]),
                                 json={"prefer_master_cabinet": True})
        assert upd.status_code == 200, upd.text
        assert upd.json()["prefer_master_cabinet"] is True

        login2 = await client.post("/api/v1/auth/login-unified", json={
            "identifier": "+7 (999) 111-55-61",
            "password": "SecurePass123!",
        })
        assert login2.status_code == 200, login2.text
        assert claim(login2.json()["access_token"])["prefer_master"] is True

    async def test_unauthorized_rejected(self, client):
        assert (await client.post("/api/v1/auth/become-master",
                                  json={})).status_code in (401, 403)


class TestAutoConfirm:
    async def test_cabinet_booking_confirmed_when_enabled(
        self, client, session,
    ):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User, UserRole
        from app.modules.auth.token import create_access_token
        from app.utils.security import hash_password
        from datetime import datetime, timedelta, timezone

        mu = User(name="AC Master", email="ac_master@example.com",
                  phone="+7 (999) 111-22-33",
                  hashed_password=hash_password("Password1!"),
                  role=UserRole.MASTER, is_active=True)
        session.add(mu)
        await session.flush()
        session.add(MasterProfile(user_id=mu.id, auto_confirm=True))
        await session.flush()
        mp_id = (await session.execute(
            select(MasterProfile.id).where(MasterProfile.user_id == mu.id)
        )).scalar_one()
        svc = Service(master_id=mp_id, name="Cut",
                      duration_minutes=60, price=500)
        session.add(svc)
        cu = User(name="AC Client", email="ac_client@example.com",
                  phone="+7 (999) 111-44-55",
                  hashed_password=hash_password("Password1!"),
                  role=UserRole.CLIENT, is_active=True)
        session.add(cu)
        await session.commit()
        token = create_access_token({"sub": str(cu.id), "role": "CLIENT",
                                     "name": cu.name, "is_admin": False})
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post(
            "/api/v1/client/appointments",
            headers={"Authorization": f"Bearer {token}"}, json={
                "master_id": mp_id, "service_id": svc.id,
                "appointment_date": dt,
            })
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "confirmed"

    async def test_profile_toggle_roundtrip(self, client, session):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.user import User, UserRole
        from app.modules.auth.token import create_access_token
        from app.utils.security import hash_password

        mu = User(name="AC Master 2", email="ac_master2@example.com",
                  phone="+7 (999) 111-66-77",
                  hashed_password=hash_password("Password1!"),
                  role=UserRole.MASTER, is_active=True)
        session.add(mu)
        await session.flush()
        session.add(MasterProfile(user_id=mu.id))
        await session.commit()
        token = create_access_token({"sub": str(mu.id), "role": "MASTER",
                                     "name": mu.name, "is_admin": False})
        h = {"Authorization": f"Bearer {token}"}
        r = await client.patch("/api/v1/admin/profile",
                               json={"auto_confirm": True}, headers=h)
        assert r.status_code == 200, r.text
        assert r.json()["auto_confirm"] is True


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

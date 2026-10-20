"""Tests for dual-role accounts (master acts as client, client upgrades)."""
import pytest


@pytest.fixture
async def master_token(client, session):
    """Master registered via API, returns a directly minted access token."""
    from sqlalchemy import select
    from app.models.user import User
    from app.modules.auth.token import create_access_token

    reg = await client.post("/api/v1/auth/register", json={
        "name": "Dual Master", "email": "dual_master@example.com",
        "password": "SecurePass123!", "phone": "+79991114444",
        "role": "MASTER",
    })
    assert reg.status_code == 201, reg.text
    user = (await session.execute(
        select(User).where(User.email == "dual_master@example.com")
    )).scalar_one()
    return create_access_token({
        "sub": str(user.id), "role": "MASTER", "name": user.name,
        "last_name": user.last_name, "is_admin": False,
    })


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
    """Draft profile + self-activation (1.83.0), no admin approval."""

    @staticmethod
    def _payload(**over):
        data = {
            "name": "Тест",
            "last_name": "Клиент",
            "cabinet_address": "ул. Тестовая, 1",
        }
        data.update(over)
        return data

    async def _register_client(self, client, session, phone, email,
                               social=True):
        """Create a CLIENT with a phone, an unverified email and optionally VK."""
        from app.services.contacts import find_user_by_contact

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
        user = await find_user_by_contact(session, "phone", phone)
        assert user is not None
        if social:
            user.vk_user_id = int(phone[-7:])
        await session.commit()
        return token, add.json()["id"], user

    async def _verify_email(self, session, contact_id):
        from app.models.user_contact import UserContact

        contact = await session.get(UserContact, contact_id)
        assert contact is not None
        contact.is_verified = True
        contact.verified_via = "code"
        await session.commit()

    async def _bind_vk(self, session, user, uid):
        user.vk_user_id = uid
        await session.commit()

    async def test_incomplete_draft_saves_without_activation(self, client, session):
        from sqlalchemy import select
        from app.models.user import UserRole
        from app.models.master_profile import MasterProfile

        token, _, user = await self._register_client(
            client, session, "+79991115555", "draft@example.com", social=False)

        # Only an address: the draft endpoint accepts a half-filled profile.
        r = await client.patch(
            "/api/v1/auth/become-master",
            headers=_auth(token),
            json={"cabinet_address": "ул. Тестовая, 1"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "draft"
        assert body["can_activate"] is False
        assert body["readiness"]["names"] is False
        assert body["readiness"]["verified_email"] is False
        assert body["readiness"]["social"] is False

        await session.refresh(user)
        assert user.role == UserRole.CLIENT
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        assert mp.is_active is False and mp.status == "inactive"
        assert mp.cabinet_address == "ул. Тестовая, 1"

        # Still a client: no panel and no public listing.
        assert (await client.get("/api/v1/admin/profile",
                                 headers=_auth(token))).status_code == 401
        pub = await client.get("/api/v1/masters/")
        assert all(m["user_id"] != user.id for m in pub.json())

        # Activation is blocked and names the missing conditions.
        act = await client.post(
            "/api/v1/auth/become-master/activate",
            headers=_auth(token),
            json=self._payload(),
        )
        assert act.status_code == 400, act.text
        detail = act.json()["detail"].lower()
        assert "почт" in detail and "соцсет" in detail

    async def test_activation_requires_verified_email(
        self, client, session, super_admin_headers,
    ):
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile

        token, email_id, user = await self._register_client(
            client, session, "+79991115556", "activate@example.com")

        # Social binding and names/address/phone are present, but the email
        # is only an unverified row: the old green tick must not appear.
        r = await client.post(
            "/api/v1/auth/become-master/activate",
            headers=_auth(token),
            json=self._payload(prefer_master_cabinet=False),
        )
        assert r.status_code == 400, r.text
        assert "почт" in r.json()["detail"].lower()

        await self._verify_email(session, email_id)
        ok = await client.post(
            "/api/v1/auth/become-master/activate",
            headers=_auth(token),
            json=self._payload(prefer_master_cabinet=False),
        )
        assert ok.status_code == 200, ok.text
        result = ok.json()
        assert result["status"] == "active"
        assert result["can_activate"] is False
        assert result["profile"]["prefer_master_cabinet"] is False
        assert client.cookies.get("access_token") == result["access_token"]

        import jwt
        from app.config import settings

        claims = jwt.decode(result["access_token"], settings.SECRET_KEY,
                            algorithms=[settings.ALGORITHM])
        assert claims["role"] == "MASTER"
        assert claims["prefer_master"] is False

        await session.refresh(user)
        assert user.role == UserRole.MASTER
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        assert mp.is_active is True and mp.status == "active"

        # Master list shows active masters only; no application marker.
        masters = await client.get("/api/v1/admin/masters",
                                   headers=super_admin_headers)
        assert masters.status_code == 200, masters.text
        row = next(m for m in masters.json() if m["user_id"] == user.id)
        assert row["status"] == "active"
        assert "is_application" not in row

        state = await client.get("/api/v1/auth/become-master", headers=_auth(token))
        assert state.status_code == 200, state.text
        assert state.json()["status"] == "active"

        pub = await client.get("/api/v1/masters/")
        assert any(m["user_id"] == user.id for m in pub.json())

    async def test_activation_requires_social(self, client, session):
        token, email_id, user = await self._register_client(
            client, session, "+79991115557", "social@example.com", social=False)
        await self._verify_email(session, email_id)

        r = await client.post(
            "/api/v1/auth/become-master/activate",
            headers=_auth(token),
            json=self._payload(),
        )
        assert r.status_code == 400, r.text
        assert "соцсет" in r.json()["detail"].lower()

        await self._bind_vk(session, user, 115557)
        ok = await client.post(
            "/api/v1/auth/become-master/activate",
            headers=_auth(token),
            json=self._payload(),
        )
        assert ok.status_code == 200, ok.text
        assert ok.json()["status"] == "active"

    async def test_photo_upload_and_draft_save(self, client, session):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile

        token, email_id, user = await self._register_client(
            client, session, "+79991115558", "photo@example.com")
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

        saved = await client.patch(
            "/api/v1/auth/become-master",
            headers=_auth(token),
            json=self._payload(avatar_url=url, avatar_preset=None),
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["profile"]["avatar_url"] == url

        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        assert mp.avatar_url == url

        # Tests must not litter the repo.
        import os as _os

        _os.remove(_os.path.join(
            "app", "static", "avatars", _os.path.basename(url)))

    async def test_admin_list_has_no_draft_and_cannot_activate_it(
        self, client, session, super_admin_headers,
    ):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile

        token, _, user = await self._register_client(
            client, session, "+79991115559", "list@example.com")
        await client.patch("/api/v1/auth/become-master",
                           headers=_auth(token), json=self._payload())

        listed = await client.get("/api/v1/admin/masters",
                                  headers=super_admin_headers)
        assert listed.status_code == 200, listed.text
        assert all(m["user_id"] != user.id for m in listed.json())
        assert all("is_application" not in m for m in listed.json())

        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user.id)
        )).scalar_one()
        manual = await client.post(
            f"/api/v1/admin/masters/{mp.id}/toggle-active",
            headers=super_admin_headers,
        )
        assert manual.status_code == 400, manual.text
        assert "самим клиентом" in manual.json()["detail"]

    async def test_landing_preference_can_be_changed_after_activation(
        self, client, session,
    ):
        token, email_id, _ = await self._register_client(
            client, session, "+79991115560", "landing@example.com")
        await self._verify_email(session, email_id)
        act = await client.post(
            "/api/v1/auth/become-master/activate",
            headers=_auth(token),
            json=self._payload(prefer_master_cabinet=False),
        )
        assert act.status_code == 200, act.text
        master_token = act.json()["access_token"]
        upd = await client.patch("/api/v1/admin/profile",
                                 headers=_auth(master_token),
                                 json={"prefer_master_cabinet": True})
        assert upd.status_code == 200, upd.text
        assert upd.json()["prefer_master_cabinet"] is True

    async def test_master_password_login_is_blocked(self, client, session):
        from app.models.user import User, UserRole
        from app.modules.auth.token import create_access_token
        from app.utils.security import hash_password

        master = User(
            name="Social Master", email="social-master@example.com",
            phone="+7 (999) 111-55-61",
            hashed_password=hash_password("SecurePass123!"),
            role=UserRole.MASTER, is_active=True, vk_user_id=115561,
        )
        session.add(master)
        await session.commit()

        for path, payload in (
            ("/api/v1/auth/login",
             {"email": "social-master@example.com",
              "password": "SecurePass123!"}),
            ("/api/v1/auth/login-unified",
             {"identifier": "social-master@example.com",
              "password": "SecurePass123!"}),
        ):
            r = await client.post(path, json=payload)
            assert r.status_code == 403, (path, r.text)
            assert "vk" in r.json()["detail"].lower()

        status = await client.post("/api/v1/auth/phone/status",
                                   json={"phone": "+7 (999) 111-55-61"})
        assert status.status_code == 200, status.text
        assert status.json()["state"] == "social"

        master_token = create_access_token(
            {"sub": str(master.id), "role": "MASTER",
             "name": master.name, "is_admin": False},
        )
        change = await client.post(
            "/api/v1/auth/password/change",
            headers=_auth(master_token),
            json={"current_password": "SecurePass123!",
                  "new_password": "AnotherPass123!"},
        )
        assert change.status_code == 400, change.text

    async def test_unauthorized_rejected(self, client):
        assert (await client.post("/api/v1/auth/become-master/activate",
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

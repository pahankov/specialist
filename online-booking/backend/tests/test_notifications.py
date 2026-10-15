"""Internal bell notifications (no messenger binding)."""


async def _mk_user(session, name, email, role):
    from app.models.user import User, UserRole
    from app.utils.security import hash_password

    u = User(
        name=name, email=email,
        hashed_password=hash_password("SecurePass123!"),
        phone=None, role=UserRole(role), is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


class TestBellBroadcast:
    async def test_super_to_clients_creates_rows(self, client, session, super_admin_headers):
        from app.models.master_profile import MasterProfile
        from app.models.client_profile import ClientProfile
        from app.models.notification import Notification
        from sqlalchemy import select, func

        c1 = await _mk_user(session, "C1", "cb1@example.com", "CLIENT")
        c2 = await _mk_user(session, "C2", "cb2@example.com", "CLIENT")
        m = await _mk_user(session, "M", "mb@example.com", "MASTER")
        session.add(ClientProfile(user_id=c1.id))
        session.add(ClientProfile(user_id=c2.id))
        session.add(MasterProfile(user_id=m.id))
        await session.commit()

        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "clients", "text": "Hello inbox"},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 2
        assert body["created"] == 2

        n = (await session.execute(
            select(func.count(Notification.id)).where(Notification.recipient_id == c1.id)
        )).scalar()
        assert n == 1

    async def test_master_all_forbidden(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "all", "text": "hi"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    async def test_master_my_clients(self, client, auth_headers):
        # Own = created by me (created_by stamp) even with no bookings yet.
        created = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Mine", "phone": "+79990001234"},
            headers=auth_headers,
        )
        assert created.status_code == 201, created.text
        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "my_clients", "text": "Master news"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["created"] >= 1

    async def test_master_selected_only_own(self, client, session, auth_headers):
        own = await client.post(
            "/api/v1/admin/clients",
            json={"name": "Own", "phone": "+79990004321"},
            headers=auth_headers,
        )
        assert own.status_code == 201, own.text
        stranger = await _mk_user(session, "Stranger", "strangerx@example.com", "CLIENT")
        await session.commit()
        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "selected",
                  "user_ids": [own.json()["id"], stranger.id], "text": "Hi"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["skipped_not_allowed"] == 1

    async def test_inbox_and_read(self, client, session, super_admin_headers):
        from sqlalchemy import select
        from app.models.notification import Notification
        from app.models.user import User

        me = (await session.execute(
            select(User).where(User.email == "superadmin@example.com")
        )).scalar_one()
        session.add(Notification(sender_id=None, recipient_id=me.id,
                                 text="Ping", audience="all"))
        await session.commit()

        r = await client.get("/api/v1/admin/notifications/inbox", headers=super_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["unread"] >= 1
        nid = r.json()["items"][0]["id"]

        u = await client.get("/api/v1/admin/notifications/unread-count",
                             headers=super_admin_headers)
        assert u.json()["unread"] >= 1

        mr = await client.post(f"/api/v1/admin/notifications/{nid}/read",
                               headers=super_admin_headers)
        assert mr.status_code == 200
        assert mr.json()["is_read"] is True

    async def test_inbox_with_sender_no_500(self, client, session, super_admin_headers):
        """Rows WITH sender_id must not 500 (lazy .sender raised
        MissingGreenlet — real prod crash, sender-less rows masked it)."""
        from sqlalchemy import select
        from app.models.notification import Notification
        from app.models.user import User

        me = (await session.execute(
            select(User).where(User.email == "superadmin@example.com")
        )).scalar_one()
        other = await _mk_user(session, "Sender", "sender@example.com", "MASTER")
        await session.commit()
        session.add(Notification(sender_id=other.id, recipient_id=me.id,
                                 text="Новая запись", audience="booking",
                                 link="appointments"))
        await session.commit()
        # Detach everything: rows must serialize from fresh SELECTs.
        session.expunge_all()

        r = await client.get("/api/v1/admin/notifications/inbox",
                             headers=super_admin_headers)
        assert r.status_code == 200, r.text
        items = [i for i in r.json()["items"] if i["text"] == "Новая запись"]
        assert len(items) == 1
        assert items[0]["sender_name"] == "Sender"
        assert items[0]["link"] == "appointments"

        mr = await client.post(
            f"/api/v1/admin/notifications/{items[0]['id']}/read",
            headers=super_admin_headers)
        assert mr.status_code == 200, mr.text
        assert mr.json()["is_read"] is True
        assert mr.json()["sender_name"] == "Sender"

    async def test_audience_counts(self, client, super_admin_headers):
        r = await client.get(
            "/api/v1/admin/notifications/audience-counts",
            params={"audience": "masters"},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        assert "total" in r.json()

    async def test_sent_history(self, client, session, super_admin_headers):
        from app.models.master_profile import MasterProfile
        from app.models.client_profile import ClientProfile

        c1 = await _mk_user(session, "H1", "h1x@example.com", "CLIENT")
        session.add(ClientProfile(user_id=c1.id))
        await session.commit()

        b = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "clients", "text": "History check"},
            headers=super_admin_headers,
        )
        assert b.status_code == 200, b.text

        r = await client.get(
            "/api/v1/admin/notifications/sent", headers=super_admin_headers
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert len(items) >= 1
        first = items[0]
        assert first["text"] == "History check"
        assert first["audience"] == "clients"
        assert first["recipient_count"] >= 1
        assert any(x["id"] == c1.id for x in first["recipients"])
        assert first["created_at"]

    async def test_sent_history_is_own_only(self, client, auth_headers, super_admin_headers):
        await client.post(
            "/api/v1/admin/clients",
            json={"name": "Own Hist", "phone": "+79990007766"},
            headers=auth_headers,
        )
        b = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "my_clients", "text": "Master news"},
            headers=auth_headers,
        )
        assert b.status_code == 200, b.text

        mine = await client.get(
            "/api/v1/admin/notifications/sent", headers=auth_headers
        )
        assert any(i["text"] == "Master news" for i in mine.json()["items"])

        others = await client.get(
            "/api/v1/admin/notifications/sent", headers=super_admin_headers
        )
        assert all(i["text"] != "Master news" for i in others.json()["items"])


class TestClientInbox:
    async def _login_client(self, client, session):
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        u = User(name="Cab", email="cabinbox@example.com",
                 hashed_password=hash_password("SecurePass123!"),
                 phone="+79990001199", role=UserRole.CLIENT, is_active=True)
        session.add(u)
        await session.commit()
        token = create_access_token({"sub": str(u.id), "role": "CLIENT",
                                     "name": u.name, "is_admin": False})
        return {"Authorization": f"Bearer {token}"}, u.id

    async def test_client_inbox_flow(self, client, session):
        from app.models.notification import Notification

        headers, uid = await self._login_client(client, session)
        session.add(Notification(sender_id=None, recipient_id=uid, text="Hello client"))
        await session.commit()

        r = await client.get("/api/v1/client/notifications/inbox", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["unread"] == 1

        nid = r.json()["items"][0]["id"]
        mr = await client.post(f"/api/v1/client/notifications/{nid}/read", headers=headers)
        assert mr.status_code == 200

        u = await client.get("/api/v1/client/notifications/unread-count", headers=headers)
        assert u.json()["unread"] == 0


class TestClientInboxIsolation:
    """Cabinet bells: each client sees only her own booking bells."""

    async def _master_headers(self, u):
        from app.modules.auth.token import create_access_token
        token = create_access_token({"sub": str(u.id), "role": "MASTER",
                                     "name": u.name, "is_admin": False})
        return {"Authorization": f"Bearer {token}"}

    async def _client_headers(self, session, name, email, phone):
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        u = User(name=name, email=email,
                 hashed_password=hash_password("SecurePass123!"),
                 phone=phone, role=UserRole.CLIENT, is_active=True)
        session.add(u)
        await session.commit()
        token = create_access_token({"sub": str(u.id), "role": "CLIENT",
                                     "name": u.name, "is_admin": False})
        return {"Authorization": f"Bearer {token}"}, u

    async def test_confirm_bell_reaches_only_booking_client(self, client, session):
        from datetime import datetime, timedelta
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.service import Service

        m = await _mk_user(session, "IsoMaster", "isomaster@example.com", "MASTER")
        session.add(MasterProfile(user_id=m.id, status="active"))
        await session.flush()
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == m.id))).scalar_one()
        s = Service(master_id=mp.id, name="IsoCut", duration_minutes=60,
                    price=1000, is_active=True)
        session.add(s)
        await session.commit()

        ha, _a = await self._client_headers(session, "IsoA", "isoa@example.com",
                                            "+79990009001")
        hb, _b = await self._client_headers(session, "IsoB", "isob@example.com",
                                            "+79990009002")

        day = (datetime.now() + timedelta(days=3)).replace(
            hour=10, minute=0, second=0, microsecond=0).isoformat()
        r = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id, "appointment_date": day},
            headers=ha,
        )
        assert r.status_code == 201, r.text
        appt_id = r.json()["id"]

        c = await client.patch(f"/api/v1/admin/appointments/{appt_id}/confirm",
                               headers=await self._master_headers(m))
        assert c.status_code == 200, c.text

        ia = await client.get("/api/v1/client/notifications/inbox", headers=ha)
        assert ia.status_code == 200, ia.text
        texts_a = [i["text"] for i in ia.json()["items"]]
        assert any("IsoMaster" in t and "IsoCut" in t for t in texts_a), texts_a

        ib = await client.get("/api/v1/client/notifications/inbox", headers=hb)
        assert ib.status_code == 200, ib.text
        assert ib.json()["items"] == []
        assert ib.json()["unread"] == 0

    async def test_client_sender_bells_hidden_in_cabinet(self, client, session):
        from app.models.notification import Notification

        hx, x = await self._client_headers(session, "IsoX", "isox@example.com",
                                           "+79990009003")
        other = await _mk_user(session, "IsoClient", "isoclient@example.com", "CLIENT")
        await session.commit()
        session.add(Notification(sender_id=other.id, recipient_id=x.id,
                                 text="client chatter", audience="booking"))
        await session.commit()

        r = await client.get("/api/v1/client/notifications/inbox", headers=hx)
        assert r.status_code == 200, r.text
        assert all(i["text"] != "client chatter" for i in r.json()["items"])
        assert r.json()["unread"] == 0

    async def test_clear_deletes_only_own(self, client, session):
        from app.models.notification import Notification

        ha, a = await self._client_headers(session, "IsoC", "isoc@example.com",
                                           "+79990009004")
        hb, b = await self._client_headers(session, "IsoD", "isod@example.com",
                                           "+79990009005")
        session.add(Notification(sender_id=None, recipient_id=a.id, text="mine"))
        session.add(Notification(sender_id=None, recipient_id=b.id, text="theirs"))
        await session.commit()

        d = await client.delete("/api/v1/client/notifications", headers=ha)
        assert d.status_code == 200, d.text
        assert d.json()["deleted"] == 1

        rb = await client.get("/api/v1/client/notifications/inbox", headers=hb)
        assert [i["text"] for i in rb.json()["items"]] == ["theirs"]

    async def test_clear_sent_keeps_recipient_bells(self, client, session,
                                                   super_admin_headers):
        from app.models.client_profile import ClientProfile
        from app.models.notification import Notification
        from sqlalchemy import select, func

        c1 = await _mk_user(session, "SC1", "sc1@example.com", "CLIENT")
        session.add(ClientProfile(user_id=c1.id))
        await session.commit()

        b = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "clients", "text": "Sent clear check"},
            headers=super_admin_headers,
        )
        assert b.status_code == 200, b.text

        d = await client.delete("/api/v1/admin/notifications/sent",
                                headers=super_admin_headers)
        assert d.status_code == 200, d.text
        assert d.json()["deleted"] >= 1

        s = await client.get("/api/v1/admin/notifications/sent",
                             headers=super_admin_headers)
        assert s.json()["items"] == []

        # Recipient bells survive the history cleanup.
        n = (await session.execute(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == c1.id)
        )).scalar()
        assert n >= 1

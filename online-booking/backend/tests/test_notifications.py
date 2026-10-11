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

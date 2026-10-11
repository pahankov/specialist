"""Broadcast notifications via MAX (super/master audiences)."""
import pytest


@pytest.fixture
def fake_max(monkeypatch):
    sent = []

    class FakeApi:
        enabled = True

        async def send_message(self, user_id: int, text: str, attachments=None):
            sent.append((user_id, text))
            return {"ok": True}

    import app.modules.admin.notifications as notif

    monkeypatch.setattr(notif, "get_max_api", lambda: FakeApi())
    return sent


async def _mk_user(session, name, email, role, max_uid=None):
    from app.models.user import User, UserRole
    from app.utils.security import hash_password

    u = User(
        name=name, email=email,
        hashed_password=hash_password("SecurePass123!"),
        phone=None, role=UserRole(role),
        max_user_id=max_uid, is_active=True,
    )
    session.add(u)
    await session.flush()
    return u


class TestBroadcast:
    async def test_super_to_clients(self, client, session, super_admin_headers, fake_max):
        from app.models.master_profile import MasterProfile
        from app.models.client_profile import ClientProfile

        c1 = await _mk_user(session, "C1", "c1n@example.com", "CLIENT", max_uid=111)
        c2 = await _mk_user(session, "C2", "c2n@example.com", "CLIENT", max_uid=None)
        m = await _mk_user(session, "M", "mn@example.com", "MASTER", max_uid=222)
        session.add(ClientProfile(user_id=c1.id))
        session.add(ClientProfile(user_id=c2.id))
        session.add(MasterProfile(user_id=m.id))
        await session.commit()

        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "clients", "text": "Hello clients"},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 2
        assert body["sent"] == 1
        assert body["skipped_no_max"] == 1
        assert fake_max == [(111, "Hello clients")]

    async def test_master_all_forbidden(self, client, auth_headers):
        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "all", "text": "hi"},
            headers=auth_headers,
        )
        assert r.status_code == 403

    async def test_master_my_clients_fallback(self, client, session, auth_headers, fake_max):
        # auth master has no bookings: falls back to visible CLIENTs
        await _mk_user(session, "C9", "c9n@example.com", "CLIENT", max_uid=999)
        await session.commit()
        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "my_clients", "text": "Master news"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["sent"] >= 1

    async def test_master_selected_only_clients(
        self, client, session, auth_headers, fake_max
    ):
        c = await _mk_user(session, "CS", "csn@example.com", "CLIENT", max_uid=555)
        m2 = await _mk_user(session, "M2", "m2n@example.com", "MASTER", max_uid=666)
        await session.commit()
        r = await client.post(
            "/api/v1/admin/notifications/broadcast",
            json={"audience": "selected", "user_ids": [c.id, m2.id], "text": "Hi"},
            headers=auth_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["total"] == 1
        assert body["skipped_not_allowed"] == 1
        assert fake_max == [(555, "Hi")]

    async def test_audience_counts(self, client, super_admin_headers):
        r = await client.get(
            "/api/v1/admin/notifications/audience-counts",
            params={"audience": "masters"},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        assert "total" in r.json()

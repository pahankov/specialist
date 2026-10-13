"""Tests for per-master client hiding (remove from my lists, keep history)."""
import pytest
from datetime import datetime, timedelta, timezone


def _dt(days=1):
    return datetime.now(timezone.utc) + timedelta(days=days)


async def _register(client, session, name, email, phone, is_master):
    from sqlalchemy import select
    from app.models.user import User
    r = await client.post("/api/v1/auth/register-unified", json={
        "name": name, "email": email, "phone": phone,
        "password": "SecurePass123!", "is_master": is_master,
    })
    assert r.status_code == 201, r.text
    user_id = (await session.execute(
        select(User.id).where(User.email == email)
    )).scalar_one()
    return {"access_token": r.json()["access_token"], "id": user_id}


async def _mp_id(session, user_id):
    from sqlalchemy import select
    from app.models.master_profile import MasterProfile
    return (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == user_id)
    )).scalar_one().id


async def _cp_id(session, user_id):
    from sqlalchemy import select
    from app.models.client_profile import ClientProfile
    return (await session.execute(
        select(ClientProfile).where(ClientProfile.user_id == user_id)
    )).scalar_one().id


@pytest.fixture
async def hide_setup(client, session):
    """Master A + master B + client; client has past+future with A, past with B."""
    from app.models.appointment import Appointment
    from app.models.service import Service

    a = await _register(client, session, "Master A", "hide_a@example.com",
                        "+79991110001", True)
    b = await _register(client, session, "Master B", "hide_b@example.com",
                        "+79991110002", True)
    c = await _register(client, session, "Hide Client", "hide_c@example.com",
                        "+79991110003", False)
    mp_a = await _mp_id(session, a["id"])
    mp_b = await _mp_id(session, b["id"])
    cp = await _cp_id(session, c["id"])

    svc_a = Service(master_id=mp_a, name="Cut",
                    duration_minutes=60, price=1000)
    svc_b = Service(master_id=mp_b, name="Cut",
                    duration_minutes=60, price=1000)
    session.add_all([svc_a, svc_b])
    await session.flush()
    session.add_all([
        Appointment(master_id=mp_a, service_id=svc_a.id, client_id=cp,
                    appointment_date=_dt(2), status="pending"),
        Appointment(master_id=mp_a, service_id=svc_a.id, client_id=cp,
                    appointment_date=_dt(-2), status="completed"),
        Appointment(master_id=mp_b, service_id=svc_b.id, client_id=cp,
                    appointment_date=_dt(-3), status="completed"),
    ])
    await session.commit()
    return {
        "a": a, "b": b, "c": c, "mp_a": mp_a, "mp_b": mp_b, "cp": cp,
    }


def _auth(token_resp):
    return {"Authorization": f"Bearer {token_resp['access_token']}"}


class TestMasterHide:
    async def test_hide_removes_from_lists_keeps_history(
        self, client, session, hide_setup,
    ):
        from sqlalchemy import select
        from app.models.appointment import Appointment
        from app.models.user import User

        s = hide_setup
        headers_a = _auth(s["a"])
        client_uid = (s["c"]["id"])

        r = await client.delete(f"/api/v1/admin/clients/{client_uid}",
                                headers=headers_a)
        assert r.status_code == 204, r.text

        # Gone from A's clients list…
        lst = await client.get("/api/v1/admin/clients", headers=headers_a)
        assert lst.status_code == 200
        assert all(i["id"] != client_uid for i in lst.json()["items"])

        # …but the account is alive and past is kept.
        user = (await session.execute(
            select(User).where(User.id == client_uid))).scalar_one()
        assert user.is_active is True
        assert user.email == "hide_c@example.com"

        appts = (await session.execute(
            select(Appointment)
            .where(Appointment.client_id == s["cp"])
            .order_by(Appointment.appointment_date)
        )).scalars().all()
        by_status = {a.status for a in appts}
        assert "cancelled" in by_status  # future with A
        assert "completed" in by_status  # past kept

    async def test_hidden_renders_anonymized_for_hider_only(
        self, client, hide_setup,
    ):
        s = hide_setup
        client_uid = (s["c"]["id"])
        r = await client.delete(f"/api/v1/admin/clients/{client_uid}",
                                headers=_auth(s["a"]))
        assert r.status_code == 204

        for headers, expect in ((_auth(s["a"]), "Удалённый клиент"),
                               (_auth(s["b"]), "Hide Client")):
            lst = await client.get("/api/v1/admin/appointments",
                                   headers=headers)
            assert lst.status_code == 200
            mine = [i for i in lst.json()["items"]
                    if i["client_id"] == s["cp"]]
            assert mine, headers
            assert all(i["client_name"] == expect for i in mine), mine
            if expect == "Удалённый клиент":
                assert all(i["client_phone"] is None for i in mine)

    async def test_client_stays_active_for_self(
        self, client, hide_setup,
    ):
        s = hide_setup
        client_uid = (s["c"]["id"])
        await client.delete(f"/api/v1/admin/clients/{client_uid}",
                            headers=_auth(s["a"]))
        me = await client.get("/api/v1/client/me", headers=_auth(s["c"]))
        assert me.status_code == 200
        assert me.json()["email"] == "hide_c@example.com"

    async def test_rebooking_unhides(self, client, session, hide_setup):
        from sqlalchemy import select
        from app.models.service import Service

        s = hide_setup
        client_uid = (s["c"]["id"])
        await client.delete(f"/api/v1/admin/clients/{client_uid}",
                            headers=_auth(s["a"]))

        svc_id = (await session.execute(
            select(Service.id).where(Service.master_id == s["mp_a"])
        )).scalars().first()
        from datetime import timedelta
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post("/api/v1/client/appointments", headers=_auth(s["c"]), json={
            "master_id": s["mp_a"], "service_id": svc_id,
            "appointment_date": dt,
        })
        assert r.status_code == 201, r.text

        lst = await client.get("/api/v1/admin/clients", headers=_auth(s["a"]))
        assert any(i["id"] == client_uid for i in lst.json()["items"])

    async def test_foreign_client_hide_is_404(
        self, client, session, hide_setup,
    ):
        from app.models.user import User, UserRole

        stranger = User(name="Stranger", email="stranger@example.com",
                        phone="+79991110009", role=UserRole.CLIENT,
                        is_active=True)
        session.add(stranger)
        await session.commit()
        r = await client.delete(f"/api/v1/admin/clients/{stranger.id}",
                                headers=_auth(hide_setup["a"]))
        assert r.status_code == 404


class TestAdminPurge:
    async def test_admin_hard_deletes(
        self, client, session, hide_setup, super_admin_headers,
    ):
        from sqlalchemy import select
        from app.models.user import User

        client_uid = (hide_setup["c"]["id"])
        r = await client.delete(f"/api/v1/admin/clients/{client_uid}",
                                headers=super_admin_headers)
        assert r.status_code == 204, r.text
        user = (await session.execute(
            select(User).where(User.id == client_uid))).scalar_one_or_none()
        assert user is None


class TestBlacklist:
    async def test_block_bars_bookings_but_keeps_badge(
        self, client, session, hide_setup,
    ):
        from sqlalchemy import select
        from app.models.service import Service
        from datetime import timedelta

        s = hide_setup
        client_uid = s["c"]["id"]

        r = await client.post(f"/api/v1/admin/clients/{client_uid}/block",
                              headers=_auth(s["a"]))
        assert r.status_code == 200, r.text
        assert r.json()["cancelled_appointments"] == 1

        # Listed back with the badge (manageable), not vanished.
        lst = await client.get("/api/v1/admin/clients", headers=_auth(s["a"]))
        row = [i for i in lst.json()["items"] if i["id"] == client_uid]
        assert len(row) == 1 and row[0]["is_blocked"] is True

        # Cabinet booking + schedule barred…
        svc_id = (await session.execute(
            select(Service.id).where(Service.master_id == s["mp_a"])
        )).scalars().first()
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post("/api/v1/client/appointments",
                              headers=_auth(s["c"]), json={
                                  "master_id": s["mp_a"], "service_id": svc_id,
                                  "appointment_date": dt,
                              })
        assert r.status_code == 403, r.text
        r = await client.get("/api/v1/client/booking/schedule",
                             headers=_auth(s["c"]),
                             params={"master_id": s["mp_a"], "month": "2026-11"})
        assert r.status_code == 403, r.text

        # …public entry point sees a generic 404 (no block disclosure)…
        r = await client.post("/api/v1/appointments/public", json={
            "master_id": s["mp_a"], "service_id": svc_id,
            "client_name": "X", "client_phone": "+79991110003",
            "appointment_date": dt,
        })
        assert r.status_code == 404, r.text

        # …but the other master is unaffected.
        svc_b = (await session.execute(
            select(Service.id).where(Service.master_id == s["mp_b"])
        )).scalars().first()
        r = await client.post("/api/v1/client/appointments",
                              headers=_auth(s["c"]), json={
                                  "master_id": s["mp_b"], "service_id": svc_b,
                                  "appointment_date": dt,
                              })
        assert r.status_code == 201, r.text

    async def test_blocked_client_gets_bells(
        self, client, hide_setup,
    ):
        s = hide_setup
        client_uid = s["c"]["id"]
        r = await client.post(f"/api/v1/admin/clients/{client_uid}/block",
                              headers=_auth(s["a"]))
        assert r.status_code == 200, r.text

        inbox = await client.get("/api/v1/client/notifications/inbox",
                                 headers=_auth(s["c"]))
        assert inbox.status_code == 200
        texts = [i["text"] for i in inbox.json()["items"]]
        assert any("отменил вашу запись" in t for t in texts), texts
        assert any("ограничил вам запись" in t for t in texts), texts

    async def test_unblock_restores_everything(
        self, client, session, hide_setup,
    ):
        from sqlalchemy import select
        from app.models.service import Service
        from datetime import timedelta

        s = hide_setup
        client_uid = s["c"]["id"]
        await client.post(f"/api/v1/admin/clients/{client_uid}/block",
                          headers=_auth(s["a"]))
        r = await client.delete(f"/api/v1/admin/clients/{client_uid}/block",
                                headers=_auth(s["a"]))
        assert r.status_code == 200, r.text

        lst = await client.get("/api/v1/admin/clients", headers=_auth(s["a"]))
        row = [i for i in lst.json()["items"] if i["id"] == client_uid]
        assert len(row) == 1 and row[0]["is_blocked"] is False

        svc_id = (await session.execute(
            select(Service.id).where(Service.master_id == s["mp_a"])
        )).scalars().first()
        dt = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post("/api/v1/client/appointments",
                              headers=_auth(s["c"]), json={
                                  "master_id": s["mp_a"], "service_id": svc_id,
                                  "appointment_date": dt,
                              })
        assert r.status_code == 201, r.text

    async def test_master_booking_lifts_block(
        self, client, session, hide_setup,
    ):
        from sqlalchemy import select
        from app.models.service import Service
        from datetime import timedelta

        s = hide_setup
        client_uid = s["c"]["id"]
        await client.post(f"/api/v1/admin/clients/{client_uid}/block",
                          headers=_auth(s["a"]))

        svc_id = (await session.execute(
            select(Service.id).where(Service.master_id == s["mp_a"])
        )).scalars().first()
        dt = (datetime.now(timezone.utc) + timedelta(days=6)).isoformat()
        r = await client.post("/api/v1/admin/appointments/book",
                              headers=_auth(s["a"]), json={
                                  "client_id": client_uid,
                                  "service_id": svc_id,
                                  "appointment_date": dt,
                                  "status": "pending",
                              })
        assert r.status_code == 201, r.text

        lst = await client.get("/api/v1/admin/clients", headers=_auth(s["a"]))
        row = [i for i in lst.json()["items"] if i["id"] == client_uid]
        assert len(row) == 1 and row[0]["is_blocked"] is False

    async def _book_as(self, client, session, token, mp_id, days=5):
        from sqlalchemy import select
        from app.models.service import Service
        from datetime import timedelta

        svc_id = (await session.execute(
            select(Service.id).where(Service.master_id == mp_id)
        )).scalars().first()
        dt = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
        return await client.post(
            "/api/v1/client/appointments", headers=token, json={
                "master_id": mp_id, "service_id": svc_id,
                "appointment_date": dt,
            })

    async def test_admin_global_block_bars_everywhere(
        self, client, session, hide_setup, super_admin_headers,
    ):
        s = hide_setup
        client_uid = s["c"]["id"]
        r = await client.post(f"/api/v1/admin/clients/{client_uid}/block",
                              headers=super_admin_headers)
        assert r.status_code == 200, r.text
        assert r.json()["masters"] == 2

        for mp_id in (s["mp_a"], s["mp_b"]):
            r = await self._book_as(client, session, _auth(s["c"]), mp_id)
            assert r.status_code == 403, (mp_id, r.text)

        lst = await client.get("/api/v1/admin/clients",
                               headers=super_admin_headers)
        row = [i for i in lst.json()["items"] if i["id"] == client_uid]
        assert len(row) == 1 and row[0]["is_blocked"] is True

    async def test_admin_scoped_block_and_global_unblock(
        self, client, session, hide_setup, super_admin_headers,
    ):
        s = hide_setup
        client_uid = s["c"]["id"]
        r = await client.post(
            f"/api/v1/admin/clients/{client_uid}/block",
            headers=super_admin_headers, params={"master_id": s["mp_b"]})
        assert r.status_code == 200, r.text

        r = await self._book_as(client, session, _auth(s["c"]), s["mp_a"])
        assert r.status_code == 201, r.text
        r = await self._book_as(client, session, _auth(s["c"]), s["mp_b"],
                                days=6)
        assert r.status_code == 403, r.text

        r = await client.delete(f"/api/v1/admin/clients/{client_uid}/block",
                                headers=super_admin_headers)
        assert r.status_code == 200, r.text
        r = await self._book_as(client, session, _auth(s["c"]), s["mp_b"],
                                days=7)
        assert r.status_code == 201, r.text


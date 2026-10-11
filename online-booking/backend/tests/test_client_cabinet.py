"""Tests for client self-service endpoints (/api/v1/client/*)."""
import pytest
from datetime import datetime, timedelta, timezone


def _dt(days=1):
    return datetime.now(timezone.utc) + timedelta(days=days)


@pytest.fixture
async def client_user(session):
    """Client user + profile, returns (user_id, headers)."""
    from app.models.user import User, UserRole
    from app.models.client_profile import ClientProfile
    from app.modules.auth.token import create_access_token

    user = User(
        name="Client One", email="c1@example.com", phone="+79990001111",
        hashed_password=None, role=UserRole.CLIENT,
        is_active=True, is_verified=True,
    )
    session.add(user)
    await session.flush()
    session.add(ClientProfile(user_id=user.id))
    await session.commit()
    token = create_access_token({
        "sub": str(user.id), "role": "CLIENT", "name": user.name,
        "is_admin": False,
    })
    return user.id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def seeded_appointments(session, client_user):
    """Own master+service+appointments (unique emails, no fixture clash)."""
    from app.models.appointment import Appointment
    from app.models.client_profile import ClientProfile
    from app.models.master_profile import MasterProfile
    from app.models.service import Service
    from app.models.user import User, UserRole
    from app.utils.security import hash_password
    from sqlalchemy import select

    master_user = User(
        name="Cab Master", email="cabmaster@example.com", phone="+79990007777",
        hashed_password=hash_password("Password1!"), role=UserRole.MASTER,
        is_active=True, is_verified=True,
    )
    session.add(master_user)
    await session.flush()
    session.add(MasterProfile(user_id=master_user.id))
    await session.flush()
    mp = (await session.execute(
        select(MasterProfile).where(MasterProfile.user_id == master_user.id)
    )).scalar_one()

    user_id, _ = client_user
    cp = (await session.execute(
        select(ClientProfile).where(ClientProfile.user_id == user_id)
    )).scalar_one()
    service = Service(master_id=mp.id, name="Cut",
                      duration_minutes=60, price=1000)
    session.add(service)
    await session.flush()
    mine_pending = Appointment(
        master_id=mp.id, service_id=service.id, client_id=cp.id,
        appointment_date=_dt(2), status="pending")
    mine_done = Appointment(
        master_id=mp.id, service_id=service.id, client_id=cp.id,
        appointment_date=_dt(-2), status="completed")
    other_user = User(name="Other", phone="+79990002222", role="CLIENT")
    session.add(other_user)
    await session.flush()
    other_cp = ClientProfile(user_id=other_user.id)
    session.add(other_cp)
    await session.flush()
    other = Appointment(
        master_id=mp.id, service_id=service.id, client_id=other_cp.id,
        appointment_date=_dt(2), status="pending")
    session.add_all([mine_pending, mine_done, other])
    await session.commit()
    return {"pending_id": mine_pending.id, "done_id": mine_done.id,
            "other_id": other.id}


class TestClientMe:
    async def test_me_returns_profile(self, client, client_user):
        _, headers = client_user
        resp = await client.get("/api/v1/client/me", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["phone"] == "+79990001111"

    async def test_me_master_rejected(self, client, auth_headers):
        resp = await client.get("/api/v1/client/me", headers=auth_headers)
        assert resp.status_code == 401

    async def test_me_no_token_rejected(self, client):
        assert (await client.get("/api/v1/client/me")).status_code in (401, 403)


class TestMyAppointments:
    async def test_list_only_own(self, client, client_user, seeded_appointments):
        _, headers = client_user
        resp = await client.get("/api/v1/client/appointments", headers=headers)
        assert resp.status_code == 200
        ids = {a["id"] for a in resp.json()}
        assert seeded_appointments["pending_id"] in ids
        assert seeded_appointments["done_id"] in ids
        assert seeded_appointments["other_id"] not in ids

    async def test_list_has_details(self, client, client_user, seeded_appointments):
        _, headers = client_user
        resp = await client.get("/api/v1/client/appointments", headers=headers)
        first = resp.json()[0]
        assert first["service_name"] == "Cut"
        assert first["master_name"]


class TestCancelAppointment:
    async def test_cancel_own_pending(
        self, client, client_user, seeded_appointments
    ):
        _, headers = client_user
        appt_id = seeded_appointments["pending_id"]
        resp = await client.post(
            f"/api/v1/client/appointments/{appt_id}/cancel", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "cancelled"

    async def test_cancel_other_404(self, client, client_user, seeded_appointments):
        _, headers = client_user
        resp = await client.post(
            f"/api/v1/client/appointments/{seeded_appointments['other_id']}/cancel",
            headers=headers)
        assert resp.status_code == 404

    async def test_cancel_completed_400(
        self, client, client_user, seeded_appointments
    ):
        _, headers = client_user
        resp = await client.post(
            f"/api/v1/client/appointments/{seeded_appointments['done_id']}/cancel",
            headers=headers)
        assert resp.status_code == 400

    async def test_cancel_missing_404(self, client, client_user):
        _, headers = client_user
        resp = await client.post(
            "/api/v1/client/appointments/999999/cancel", headers=headers)
        assert resp.status_code == 404

    async def test_cancel_master_rejected(
        self, client, auth_headers, seeded_appointments
    ):
        resp = await client.post(
            f"/api/v1/client/appointments/{seeded_appointments['pending_id']}/cancel",
            headers=auth_headers)
        assert resp.status_code == 401


class TestClientStats:
    async def test_stats_counts(
        self, client, client_user, seeded_appointments
    ):
        _, headers = client_user
        resp = await client.get("/api/v1/client/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed_visits"] == 1
        assert data["upcoming_count"] == 1
        assert data["cancelled_count"] == 0
        assert data["total_spent"] == 1000
        assert data["favorite_master"]["visits"] == 1
        assert data["favorite_service"]["visits"] == 1

    async def test_stats_empty_new_client(self, client, session):
        from app.models.user import User, UserRole
        from app.modules.auth.token import create_access_token

        user = User(name="Fresh", phone="+79998887766", role=UserRole.CLIENT)
        session.add(user)
        await session.commit()
        token = create_access_token({
            "sub": str(user.id), "role": "CLIENT", "name": user.name,
            "is_admin": False,
        })
        resp = await client.get(
            "/api/v1/client/stats",
            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json() == {
            "total_spent": 0, "completed_visits": 0, "upcoming_count": 0,
            "cancelled_count": 0, "favorite_master": None,
            "favorite_service": None,
        }


class TestUpdateMe:
    async def test_update_name(self, client, client_user):
        _, headers = client_user
        resp = await client.patch(
            "/api/v1/client/me", json={"name": "  New Name  "},
            headers=headers)
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_update_city(self, client, client_user, session):
        from app.models.country import Country
        from app.models.city import City
        from sqlalchemy import select

        _, headers = client_user
        country = Country(code="T", name_ru="T", name_en="T", phone_prefix="+1")
        session.add(country)
        await session.flush()
        session.add(City(country_id=country.id, name_ru="Twn",
                         slug="twn", is_active=True))
        await session.commit()
        city = (await session.execute(
            select(City).where(City.slug == "twn"))).scalar_one()
        resp = await client.patch(
            "/api/v1/client/me", json={"city_id": city.id}, headers=headers)
        assert resp.status_code == 200
        assert resp.json()["city_id"] == city.id
        assert resp.json()["city_name"] == "Twn"

    async def test_update_unknown_city_404(self, client, client_user):
        _, headers = client_user
        resp = await client.patch(
            "/api/v1/client/me", json={"city_id": 999999}, headers=headers)
        assert resp.status_code == 404

    async def test_update_empty_name_422(self, client, client_user):
        _, headers = client_user
        resp = await client.patch(
            "/api/v1/client/me", json={"name": "   "}, headers=headers)
        assert resp.status_code == 422

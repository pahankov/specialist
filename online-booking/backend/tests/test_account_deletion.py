"""Tests for self-service account deletion (soft delete + retention)."""
import pytest
from datetime import datetime, timedelta, timezone


def _dt(days=1):
    return datetime.now(timezone.utc) + timedelta(days=days)


@pytest.fixture
async def client_selfdel(session):
    """Client user + profile + token (unique emails per test module)."""
    from app.models.user import User, UserRole
    from app.models.client_profile import ClientProfile
    from app.modules.auth.token import create_access_token

    user = User(
        name="Selfdel Client", email="selfdel@example.com",
        phone="+79990009911", hashed_password=None,
        role=UserRole.CLIENT, is_active=True, is_verified=True,
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
async def master_selfdel(session):
    """Master user + profile + token."""
    from app.models.user import User, UserRole
    from app.models.master_profile import MasterProfile
    from app.modules.auth.token import create_access_token
    from app.utils.security import hash_password

    user = User(
        name="Selfdel Master", email="selfdel_master@example.com",
        phone="+79990009922", hashed_password=hash_password("Password1!"),
        role=UserRole.MASTER, is_active=True, is_verified=True,
    )
    session.add(user)
    await session.flush()
    session.add(MasterProfile(user_id=user.id))
    await session.commit()
    token = create_access_token({
        "sub": str(user.id), "role": "MASTER", "name": user.name,
        "is_admin": False,
    })
    return user.id, {"Authorization": f"Bearer {token}"}


async def _seed_client_appointments(session, user_id, mp_id=None):
    """Future pending + past completed appointments for the client."""
    from sqlalchemy import select
    from app.models.appointment import Appointment
    from app.models.client_profile import ClientProfile
    from app.models.master_profile import MasterProfile
    from app.models.service import Service
    from app.models.user import User, UserRole
    from app.utils.security import hash_password

    if mp_id is None:
        mu = User(
            name="SD Master", email="sd_master@example.com",
            phone="+79990009933", hashed_password=hash_password("Password1!"),
            role=UserRole.MASTER, is_active=True, is_verified=True,
        )
        session.add(mu)
        await session.flush()
        session.add(MasterProfile(user_id=mu.id))
        await session.flush()
        mp_id = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == mu.id)
        )).scalar_one().id
    cp = (await session.execute(
        select(ClientProfile).where(ClientProfile.user_id == user_id)
    )).scalar_one()
    service = Service(master_id=mp_id, name="Cut",
                      duration_minutes=60, price=1000)
    session.add(service)
    await session.flush()
    future = Appointment(master_id=mp_id, service_id=service.id,
                         client_id=cp.id, appointment_date=_dt(2),
                         status="pending")
    past = Appointment(master_id=mp_id, service_id=service.id,
                       client_id=cp.id, appointment_date=_dt(-2),
                       status="completed")
    session.add_all([future, past])
    await session.commit()
    return future.id, past.id


class TestClientSelfDelete:
    async def test_delete_cancels_future_keeps_past(
        self, client, session, client_selfdel,
    ):
        from sqlalchemy import select
        from app.models.appointment import Appointment
        from app.models.user import User

        user_id, headers = client_selfdel
        future_id, past_id = await _seed_client_appointments(
            session, user_id)

        r = await client.delete("/api/v1/client/me", headers=headers)
        assert r.status_code == 200, r.text
        assert r.json()["cancelled_appointments"] == 1

        user = (await session.execute(
            select(User).where(User.id == user_id))).scalar_one()
        assert user.is_active is False
        assert user.deleted_at is not None
        assert user.email is None
        assert user.phone is None

        future = (await session.execute(
            select(Appointment).where(Appointment.id == future_id)
        )).scalar_one()
        past = (await session.execute(
            select(Appointment).where(Appointment.id == past_id)
        )).scalar_one()
        assert future.status == "cancelled"
        assert past.status == "completed"

    async def test_old_token_rejected_after_delete(
        self, client, client_selfdel,
    ):
        _, headers = client_selfdel
        assert (await client.delete(
            "/api/v1/client/me", headers=headers)).status_code == 200
        r = await client.get("/api/v1/client/me", headers=headers)
        assert r.status_code == 401

    async def test_phone_freed_for_reregistration(
        self, client, client_selfdel,
    ):
        user_id, headers = client_selfdel
        assert (await client.delete(
            "/api/v1/client/me", headers=headers)).status_code == 200
        # The deleted account's phone was anonymized, so re-registering the
        # same phone must now succeed.
        r = await client.post("/api/v1/auth/register-unified", json={
            "phone": "+79990009911", "password": "SecurePass123!",
            "consent": True,
        })
        assert r.status_code == 201, r.text

    async def test_unauthorized_rejected(self, client):
        r = await client.delete("/api/v1/client/me")
        assert r.status_code in (401, 403)


class TestMasterSelfDelete:
    async def test_delete_hides_profile_and_blocks_login(
        self, client, session, master_selfdel,
    ):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.user import User, UserRole

        user_id, headers = master_selfdel
        r = await client.delete("/api/v1/admin/profile", headers=headers)
        assert r.status_code == 200, r.text

        user = (await session.execute(
            select(User).where(User.id == user_id))).scalar_one()
        assert user.is_active is False
        assert user.deleted_at is not None

        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.user_id == user_id)
        )).scalar_one()
        assert mp.is_active is False
        assert mp.status == "inactive"

        # Gone from the public listing.
        pub = await client.get("/api/v1/masters/")
        assert pub.status_code == 200
        assert all(m["id"] != mp.id for m in pub.json())

        # Password login no longer finds the account.
        r = await client.post("/api/v1/auth/login", json={
            "email": "selfdel_master@example.com",
            "password": "Password1!",
        })
        assert r.status_code in (400, 401, 404)

    async def test_admin_cannot_delete_self(
        self, client, super_admin_headers,
    ):
        r = await client.delete("/api/v1/admin/profile",
                                headers=super_admin_headers)
        assert r.status_code == 400

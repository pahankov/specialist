"""Regression: master PATCH / toggle-active / DELETE must not 500.
Covers two real prod bugs:
- status routes were mounted at /admin/{id}/... instead of
  /admin/masters/{id}/... (toggle/suspend/... all 404'd);
- block toggled only `status` while the UI reads `is_active`.
"""
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.utils.security import hash_password
from sqlalchemy import select


async def _seed_master(session, email="repro_master@example.com"):
    u = User(name="Repro", email=email,
             hashed_password=hash_password("SecurePass123!"),
             role=UserRole.MASTER)
    session.add(u)
    await session.flush()
    mp = MasterProfile(user_id=u.id)
    session.add(mp)
    await session.flush()
    await session.commit()
    return mp.id


class TestMasterMutations:
    async def test_patch_master(self, client, session, super_admin_headers):
        mp_id = await _seed_master(session)
        r = await client.patch(
            f"/api/v1/admin/masters/{mp_id}",
            json={"name": "Repro Renamed"},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Repro Renamed"

    async def test_patch_master_full_form(self, client, session, super_admin_headers):
        """Prod-shaped payload: phone, telegram, description, strong password."""
        mp_id = await _seed_master(session, "repro_full@example.com")
        r = await client.patch(
            f"/api/v1/admin/masters/{mp_id}",
            json={
                "name": "Repro Full",
                "phone": "+7 (999) 123-45-67",
                "telegram_username": "some@mail.ru",
                "description": "desc",
                "password": "StrongPass123!",
            },
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text

    async def test_toggle_master(self, client, session, super_admin_headers):
        mp_id = await _seed_master(session, "repro_toggle@example.com")
        r = await client.post(
            f"/api/v1/admin/masters/{mp_id}/toggle-active",
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Block flips BOTH flags: UI badge/icon read is_active
        assert body["is_active"] is False
        assert body["status"] == "inactive"
        r2 = await client.post(
            f"/api/v1/admin/masters/{mp_id}/toggle-active",
            headers=super_admin_headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["is_active"] is True
        assert r2.json()["status"] == "active"

    async def test_delete_master(self, client, session, super_admin_headers):
        mp_id = await _seed_master(session, "repro_del@example.com")
        r = await client.delete(
            f"/api/v1/admin/masters/{mp_id}",
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text

    async def test_delete_master_with_data(self, client, session, super_admin_headers):
        """Delete removes appointments/services too (no FK 500 on prod)."""
        from datetime import datetime, timezone
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.service import Service

        mp_id = await _seed_master(session, "repro_del_data@example.com")
        session.add(Service(master_id=mp_id, name="S", duration_minutes=60, price=1000))
        await session.flush()
        service = (await session.execute(
            select(Service).where(Service.master_id == mp_id)
        )).scalar_one()
        cuser = User(name="C", email="repro_del_client@example.com",
                     hashed_password=hash_password("SecurePass123!"),
                     role=UserRole.CLIENT)
        session.add(cuser)
        await session.flush()
        cp = ClientProfile(user_id=cuser.id)
        session.add(cp)
        await session.flush()
        session.add(Appointment(
            master_id=mp_id, service_id=service.id, client_id=cp.id,
            appointment_date=datetime.now(timezone.utc), status="pending",
        ))
        await session.commit()

        r = await client.delete(
            f"/api/v1/admin/masters/{mp_id}",
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        remaining = await session.execute(
            select(Appointment).where(Appointment.master_id == mp_id)
        )
        assert remaining.scalars().all() == []

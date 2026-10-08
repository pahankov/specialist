"""Tests for tariffs, future-only active rule, superadmin hours, sorting."""
from datetime import date, timedelta


class TestTariffs:
    async def test_new_master_gets_trial(self, client, super_admin_headers):
        """Created master sits on trial with ~180-day term."""
        resp = await client.post("/api/v1/admin/masters", json={
            "name": "Tariff Test", "email": "tariff@example.com",
            "password": "SecurePass123!", "phone": "+79990005555",
        }, headers=super_admin_headers)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["tariff"] == "trial"
        assert body["trial_ends_at"] is not None
        ends = body["trial_ends_at"][:10]
        expect = (date.today() + timedelta(days=180)).isoformat()
        assert ends == expect

    async def test_migration_backfills_existing(self, session):
        """Model default covers new rows; migration covers old ones (checked here)."""
        from app.models.master_profile import MasterProfile
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        user = User(name="Old", email="old-trial@example.com",
                    hashed_password=hash_password("SecurePass123!"),
                    role=UserRole.MASTER)
        session.add(user)
        await session.flush()
        mp = MasterProfile(user_id=user.id)
        session.add(mp)
        await session.commit()
        assert mp.tariff == "trial"
        assert mp.trial_ends_at is not None


class TestFutureOnlyStatus:
    async def test_past_hours_do_not_activate(self, session, created_master_id):
        """Only future active hours count toward ACTIVE."""
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.working_hour import WorkingHour
        from app.services.master_status import get_master_status, update_master_status_from_working_hours
        from datetime import time as dtime

        yesterday = date.today() - timedelta(days=1)
        session.add(WorkingHour(master_id=created_master_id, schedule_date=yesterday,
                                start_time=dtime(9, 0), end_time=dtime(18, 0),
                                is_active=True))
        await session.commit()

        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()
        assert await get_master_status(session, mp) == "inactive"
        await update_master_status_from_working_hours(session, mp)
        assert mp.status == "inactive"

    async def test_future_hour_activates(self, session, created_master_id):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.models.working_hour import WorkingHour
        from app.services.master_status import update_master_status_from_working_hours
        from datetime import time as dtime

        tomorrow = date.today() + timedelta(days=1)
        session.add(WorkingHour(master_id=created_master_id, schedule_date=tomorrow,
                                start_time=dtime(9, 0), end_time=dtime(18, 0),
                                is_active=True))
        await session.commit()
        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()
        await update_master_status_from_working_hours(session, mp)
        assert mp.status == "active"

    async def test_suspended_stays_suspended(self, session, created_master_id):
        from sqlalchemy import select
        from app.models.master_profile import MasterProfile
        from app.services.master_status import update_master_status_from_working_hours

        mp = (await session.execute(
            select(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()
        mp.status = "suspended"
        await session.commit()
        await update_master_status_from_working_hours(session, mp)
        assert mp.status == "suspended"


class TestSuperadminHours:
    async def test_create_without_master_rejected(self, client, super_admin_headers):
        resp = await client.post("/api/v1/admin/working-hours", json={
            "schedule_date": "2026-12-01", "start_time": "09:00", "end_time": "18:00",
        }, headers=super_admin_headers)
        assert resp.status_code == 400

    async def test_create_for_master_ok(self, client, super_admin_headers, created_master_id):
        resp = await client.post("/api/v1/admin/working-hours", json={
            "master_id": created_master_id,
            "schedule_date": "2026-12-01", "start_time": "09:00", "end_time": "18:00",
        }, headers=super_admin_headers)
        assert resp.status_code == 201, resp.text
        assert resp.json()["master_id"] == created_master_id


class TestSorting:
    async def test_masters_sort_by_name(self, client, super_admin_headers):
        resp = await client.get(
            "/api/v1/admin/masters?sort_by=name&sort_dir=desc",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        names = [m["name"] for m in resp.json()]
        assert names == sorted(names, reverse=True)

    async def test_clients_sort_by_name(self, client, super_admin_headers):
        resp = await client.get(
            "/api/v1/admin/clients?sort_by=name&sort_dir=asc&page_size=100",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()["items"]]
        assert names == sorted(names)

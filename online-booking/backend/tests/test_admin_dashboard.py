"""Tests for admin dashboard and monthly stats endpoints."""
import pytest
from datetime import datetime, timedelta


class TestAdminDashboard:
    """Tests for GET /api/v1/admin/dashboard"""

    async def test_dashboard_empty(self, client, auth_headers):
        """Returns dashboard with zero counts when no data."""
        resp = await client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_appointments"] == 0
        assert data["total_clients"] == 0
        assert data["total_services"] == 0
        assert data["total_revenue"] == 0
        assert isinstance(data["status_counts"], dict)
        assert isinstance(data["recent_appointments"], list)
        assert isinstance(data["upcoming_appointments"], list)

    async def test_dashboard_with_data(self, client, super_admin_headers, test_service_data):
        """Dashboard reflects actual data."""
        # Create service
        service_resp = await client.post(
            "/api/v1/services/", json={**test_service_data, "master_id": 1}, headers=super_admin_headers
        )
        service_id = service_resp.json()["id"]

        resp = await client.get("/api/v1/admin/dashboard", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_services"] >= 1
        assert isinstance(data["status_counts"], dict)
        assert isinstance(data["recent_appointments"], list)


class TestAdminMonthlyStats:
    """Tests for GET /api/v1/admin/monthly-stats"""

    async def test_monthly_stats_empty(self, client, auth_headers):
        """Returns zero stats when no appointments."""
        now = datetime.now()
        resp = await client.get(
            "/api/v1/admin/monthly-stats",
            params={"year": now.year, "month": now.month},
            headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["confirmed_appointments"] == 0
        assert data["total_hours"] == 0
        assert data["revenue"] == 0

    async def test_monthly_stats_with_completed(self, client, super_admin_headers):
        """Monthly stats endpoint works."""
        now = datetime.now()
        resp = await client.get(
            "/api/v1/admin/monthly-stats",
            params={"year": now.year, "month": now.month},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "confirmed_appointments" in data
        assert "total_hours" in data
        assert "revenue" in data
        assert "cancelled_appointments" in data

    async def test_upcoming_excludes_cancelled_and_past(self, client, session, auth_headers):
        """'Ближайшие' = live future first; top_clients ranked by spending."""
        from datetime import timezone
        from sqlalchemy import select
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User

        mp = (await session.execute(select(MasterProfile))).scalar_one()
        svc = Service(master_id=mp.id, name="Top", duration_minutes=60,
                      price=2000, is_active=True)
        session.add(svc)
        await session.flush()
        cu = User(name="TopC", email="topc@example.com", phone="+79990009501",
                  role=__import__("app.models.user", fromlist=["UserRole"]).UserRole.CLIENT)
        session.add(cu)
        await session.flush()
        cp = ClientProfile(user_id=cu.id)
        session.add(cp)
        await session.flush()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session.add_all([
            Appointment(master_id=mp.id, service_id=svc.id, client_id=cp.id,
                        duration_minutes=60, price=2000,
                        appointment_date=now + timedelta(days=2), status="cancelled"),
            Appointment(master_id=mp.id, service_id=svc.id, client_id=cp.id,
                        duration_minutes=60, price=2000,
                        appointment_date=now + timedelta(days=1), status="confirmed"),
            Appointment(master_id=mp.id, service_id=svc.id, client_id=cp.id,
                        duration_minutes=60, price=1500,
                        appointment_date=now - timedelta(days=1), status="completed"),
        ])
        await session.commit()

        resp = await client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        rec = data["recent_appointments"]
        assert len(rec) == 1
        assert rec[0]["status"] == "confirmed"
        assert data["top_clients"][0]["name"] == "TopC"
        assert data["top_clients"][0]["visits"] == 1
        assert data["top_clients"][0]["spent"] == 1500.0


class TestDashboardPeriod:
    """GET /api/v1/admin/dashboard?period=... scopes appointment metrics."""

    async def _seed_two_completed(self, session):
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User, UserRole

        mp = (await session.execute(
            __import__("sqlalchemy", fromlist=["select"]).select(MasterProfile)
        )).scalar_one()
        svc = Service(master_id=mp.id, name="Period", duration_minutes=60,
                      price=1000, is_active=True)
        session.add(svc)
        await session.flush()
        cu = User(name="PeriodC", email="periodc@example.com", phone="+79990009601",
                  role=UserRole.CLIENT)
        session.add(cu)
        await session.flush()
        cp = ClientProfile(user_id=cu.id)
        session.add(cp)
        await session.flush()
        now = datetime.now()
        session.add_all([
            Appointment(master_id=mp.id, service_id=svc.id, client_id=cp.id,
                        duration_minutes=60, price=1000,
                        appointment_date=now, status="completed"),
            Appointment(master_id=mp.id, service_id=svc.id, client_id=cp.id,
                        duration_minutes=60, price=1000,
                        appointment_date=now - timedelta(days=40), status="completed"),
        ])
        await session.commit()
        return now

    async def test_period_all_sees_both(self, client, session, auth_headers):
        await self._seed_two_completed(session)
        resp = await client.get("/api/v1/admin/dashboard", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        assert resp.json()["status_counts"].get("completed") == 2

    async def test_period_today_sees_only_today(self, client, session, auth_headers):
        await self._seed_two_completed(session)
        resp = await client.get(
            "/api/v1/admin/dashboard", params={"period": "today"}, headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status_counts"].get("completed") == 1

    async def test_period_month_sees_current_month(self, client, session, auth_headers):
        now = await self._seed_two_completed(session)
        resp = await client.get(
            "/api/v1/admin/dashboard", params={"period": "month"}, headers=auth_headers
        )
        assert resp.status_code == 200, resp.text
        first_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        expected = 2 if (now - timedelta(days=40)) >= first_of_month else 1
        assert resp.json()["status_counts"].get("completed") == expected

    async def test_period_custom_window(self, client, session, auth_headers):
        now = await self._seed_two_completed(session)
        old = (now - timedelta(days=40)).date().isoformat()
        resp = await client.get(
            "/api/v1/admin/dashboard",
            params={"period": "custom", "date_from": old, "date_to": old},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status_counts"].get("completed") == 1

    async def test_period_invalid_rejected(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/admin/dashboard", params={"period": "year"}, headers=auth_headers
        )
        assert resp.status_code == 400

    async def test_period_custom_bad_dates_rejected(self, client, auth_headers):
        resp = await client.get(
            "/api/v1/admin/dashboard",
            params={"period": "custom", "date_from": "not-a-date"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        resp = await client.get(
            "/api/v1/admin/dashboard",
            params={"period": "custom", "date_from": "2026-10-10", "date_to": "2026-10-01"},
            headers=auth_headers,
        )
        assert resp.status_code == 400


class TestGlobalDashboardTopClients:
    """Superadmin dashboard carries top_clients (was missing entirely)."""

    async def test_global_top_clients_present(self, client, session, super_admin_headers):
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User, UserRole

        mu = User(name="TopM", email="topm@example.com", phone="+79990009700",
                  role=UserRole.MASTER)
        session.add(mu)
        await session.flush()
        mp = MasterProfile(user_id=mu.id)
        session.add(mp)
        await session.flush()
        svc = Service(master_id=mp.id, name="Global Top", duration_minutes=60,
                      price=3000, is_active=True)
        session.add(svc)
        await session.flush()
        cu = User(name="GlobalC", email="globalc@example.com", phone="+79990009701",
                  role=UserRole.CLIENT)
        session.add(cu)
        await session.flush()
        cp = ClientProfile(user_id=cu.id)
        session.add(cp)
        await session.flush()
        session.add(Appointment(
            master_id=mp.id, service_id=svc.id, client_id=cp.id,
            duration_minutes=60, price=3000,
            appointment_date=datetime.now(), status="completed",
        ))
        await session.commit()

        resp = await client.get("/api/v1/admin/dashboard", headers=super_admin_headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert "total_masters" in data
        top = data["top_clients"]
        assert isinstance(top, list) and len(top) >= 1
        assert top[0]["name"] == "GlobalC"
        assert top[0]["spent"] == 3000.0

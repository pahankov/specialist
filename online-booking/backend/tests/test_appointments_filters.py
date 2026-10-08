"""Regression: appointments client_id filter accepts both id spaces.

Client list responses carry User.id while Appointment.client_id stores
ClientProfile.id — the filter must resolve either.
"""
from datetime import datetime, timezone


class TestClientIdFilterSpaces:
    async def _seed(self, session, email="filterclient@example.com"):
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        muser = User(name="M", email="filtermaster@example.com",
                     hashed_password=hash_password("SecurePass123!"),
                     role=UserRole.MASTER)
        session.add(muser)
        await session.flush()
        mp = MasterProfile(user_id=muser.id)
        session.add(mp)
        await session.flush()
        service = Service(master_id=mp.id, name="S", duration_minutes=60, price=1000)
        session.add(service)
        await session.flush()
        cuser = User(name="C", email=email, phone="+79990006666",
                     hashed_password=hash_password("SecurePass123!"),
                     role=UserRole.CLIENT)
        session.add(cuser)
        await session.flush()
        cp = ClientProfile(user_id=cuser.id)
        session.add(cp)
        await session.flush()
        session.add(Appointment(
            master_id=mp.id, service_id=service.id, client_id=cp.id,
            appointment_date=datetime.now(timezone.utc), status="confirmed",
        ))
        await session.commit()
        return cuser.id, cp.id

    async def test_filter_by_user_id(self, client, session, super_admin_headers):
        user_id, _profile_id = await self._seed(session)
        resp = await client.get(
            f"/api/v1/admin/appointments?client_id={user_id}",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 1

    async def test_filter_by_profile_id(self, client, session, super_admin_headers):
        _, profile_id = await self._seed(session)
        resp = await client.get(
            f"/api/v1/admin/appointments?client_id={profile_id}",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 1

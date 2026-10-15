"""Cabinet booking: master schedule view + self booking + profile."""
from datetime import date, time, timedelta


async def _mk_master(session):
    from app.models.user import User, UserRole
    from app.models.master_profile import MasterProfile
    from app.utils.security import hash_password

    u = User(name="Book Master", email="bookmaster@example.com",
             hashed_password=hash_password("SecurePass123!"),
             phone="+79990007711", role=UserRole.MASTER, is_active=True)
    session.add(u)
    await session.flush()
    mp = MasterProfile(user_id=u.id, status="active",
                       work_start_hour=9, work_end_hour=18)
    session.add(mp)
    await session.flush()
    await session.commit()
    return u, mp


async def _client_headers(session, email="cabbook@example.com", phone="+79990007722"):
    from app.models.user import User, UserRole
    from app.utils.security import hash_password
    from app.modules.auth.token import create_access_token

    u = User(name="Cab Book", email=email,
             hashed_password=hash_password("SecurePass123!"),
             phone=phone, role=UserRole.CLIENT, is_active=True)
    session.add(u)
    await session.commit()
    token = create_access_token({"sub": str(u.id), "role": "CLIENT",
                                 "name": u.name, "is_admin": False})
    return {"Authorization": f"Bearer {token}"}, u


class TestBookingSchedule:
    async def test_schedule_shape(self, client, session):
        from app.models.service import Service
        from app.models.working_hour import WorkingHour

        _, mp = await _mk_master(session)
        session.add(Service(master_id=mp.id, name="Cut", duration_minutes=60,
                            price=1000, is_active=True))
        today = date.today()
        session.add(WorkingHour(master_id=mp.id, schedule_date=today,
                                start_time=time(9, 0), end_time=time(18, 0),
                                is_active=True))
        await session.commit()
        headers, _ = await _client_headers(session)

        r = await client.get(
            "/api/v1/client/booking/schedule",
            params={"master_id": mp.id, "month": today.strftime("%Y-%m")},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["window"] == {"start_hour": 9, "end_hour": 18}
        assert any(w["date"] == today.isoformat() for w in body["working_hours"])
        assert body["busy"] == []

    async def test_schedule_unknown_master_404(self, client, session):
        headers, _ = await _client_headers(session)
        r = await client.get(
            "/api/v1/client/booking/schedule",
            params={"master_id": 999999, "month": "2026-10"},
            headers=headers,
        )
        assert r.status_code == 404

    async def test_schedule_bad_month_400(self, client, session):
        _, mp = await _mk_master(session)
        headers, _ = await _client_headers(session)
        r = await client.get(
            "/api/v1/client/booking/schedule",
            params={"master_id": mp.id, "month": "oops"},
            headers=headers,
        )
        assert r.status_code == 400


class TestClientBook:
    async def _setup(self, client, session):
        from app.models.service import Service

        _, mp = await _mk_master(session)
        s = Service(master_id=mp.id, name="Color", duration_minutes=90,
                    price=2000, is_active=True)
        session.add(s)
        await session.commit()
        headers, u = await _client_headers(session)
        return mp, s, headers, u

    async def test_book_and_conflict(self, client, session):
        from datetime import datetime

        mp, s, headers, _ = await self._setup(client, session)
        day = (datetime.now() + timedelta(days=3)).replace(
            hour=10, minute=0, second=0, microsecond=0)

        r = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": day.isoformat()},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "pending"

        # Overlapping 90-min service at 11:00 conflicts.
        clash = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": day.replace(hour=11).isoformat()},
            headers=headers,
        )
        assert clash.status_code == 409

    async def test_book_past_rejected(self, client, session):
        from datetime import datetime

        mp, s, headers, _ = await self._setup(client, session)
        past = (datetime.now() - timedelta(days=1)).isoformat()
        r = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": past},
            headers=headers,
        )
        assert r.status_code == 400

    async def test_booked_visible_in_my_list(self, client, session):
        from datetime import datetime

        mp, s, headers, _ = await self._setup(client, session)
        day = (datetime.now() + timedelta(days=4)).replace(
            hour=12, minute=0, second=0, microsecond=0)
        await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": day.isoformat()},
            headers=headers,
        )
        mine = await client.get("/api/v1/client/appointments", headers=headers)
        assert mine.status_code == 200
        assert any(a["service_name"] == "Color" for a in mine.json())

    async def test_booking_bells_the_master(self, client, session):
        from datetime import datetime
        from sqlalchemy import select
        from app.models.notification import Notification
        from app.models.user import User

        mp, s, headers, me = await self._setup(client, session)
        master_user = (await session.execute(
            select(User).where(User.id == mp.user_id)
        )).scalar_one()
        day = (datetime.now() + timedelta(days=5)).replace(
            hour=10, minute=0, second=0, microsecond=0)
        r = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": day.isoformat()},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        notes = (await session.execute(
            select(Notification).where(Notification.recipient_id == master_user.id)
        )).scalars().all()
        assert len(notes) == 1
        assert "Новая запись" in notes[0].text
        assert notes[0].link == f"appointments:{r.json()['id']}"
        assert notes[0].sender_id == me.id


class TestClientProfilePage:
    async def test_update_name_and_address(self, client, session):
        headers, _ = await _client_headers(
            session, email="cabprof@example.com", phone="+79990007733")
        r = await client.patch(
            "/api/v1/client/me",
            json={"name": "Пётр", "last_name": "Сидоров",
                  "address": "г. Уфа, ул. Ленина, 1"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"] == "Пётр Сидоров"
        assert body["last_name"] == "Сидоров"
        assert body["address"] == "г. Уфа, ул. Ленина, 1"

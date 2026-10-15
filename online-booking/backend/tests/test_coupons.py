"""Personal coupons: issue -> bell -> preview -> booking."""
from datetime import datetime, timedelta, timezone


async def _mk_master(session):
    from app.models.user import User, UserRole
    from app.models.master_profile import MasterProfile
    from app.utils.security import hash_password
    from app.modules.auth.token import create_access_token

    m = User(name="CouponMaster", email="couponmaster@example.com",
             hashed_password=hash_password("SecurePass123!"),
             phone="+79990009301", role=UserRole.MASTER, is_active=True)
    session.add(m)
    await session.flush()
    session.add(MasterProfile(user_id=m.id, status="active"))
    await session.flush()
    mp = (await session.execute(
        __import__("sqlalchemy").select(MasterProfile).where(
            MasterProfile.user_id == m.id))).scalar_one()
    await session.commit()
    token = create_access_token({"sub": str(m.id), "role": "MASTER",
                                 "name": m.name, "is_admin": False})
    return {"Authorization": f"Bearer {token}"}, mp


async def _mk_client(session, name, email, phone):
    from app.models.user import User, UserRole
    from app.utils.security import hash_password
    from app.modules.auth.token import create_access_token

    u = User(name=name, email=email,
             hashed_password=hash_password("SecurePass123!"),
             phone=phone, role=UserRole.CLIENT, is_active=True)
    session.add(u)
    await session.commit()
    token = create_access_token({"sub": str(u.id), "role": "CLIENT",
                                 "name": u.name, "is_admin": False})
    return {"Authorization": f"Bearer {token}"}, u


class TestCoupons:
    async def _setup(self, client, session):
        from datetime import datetime, timedelta, timezone
        from app.models.service import Service

        mh, mp = await _mk_master(session)
        s = Service(master_id=mp.id, name="Cut", duration_minutes=60,
                    price=1000, is_active=True)
        session.add(s)
        await session.commit()
        ha, a = await _mk_client(session, "CA", "ca@example.com", "+79990009302")
        hb, b = await _mk_client(session, "CB", "cb@example.com", "+79990009303")
        # A becomes an own client with a real booking.
        day = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
        r = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id, "appointment_date": day},
            headers=ha,
        )
        assert r.status_code == 201, r.text
        return mh, mp, s, ha, a, hb, b

    async def test_issue_preview_book(self, client, session):
        mh, mp, s, ha, a, hb, b = await self._setup(client, session)

        r = await client.post(
            "/api/v1/admin/coupons",
            json={"kind": "percent", "value": 20, "max_uses": 1},
            headers=mh,
        )
        assert r.status_code == 201, r.text
        code = r.json()["code"]
        assert r.json()["notified"] >= 1

        # Bell reached the own client.
        inbox = await client.get("/api/v1/client/notifications/inbox", headers=ha)
        assert any(code in i["text"] for i in inbox.json()["items"])

        # Preview math.
        p = await client.post(
            "/api/v1/client/coupons/preview",
            json={"master_id": mp.id, "service_id": s.id, "code": code},
            headers=ha,
        )
        assert p.status_code == 200, p.text
        assert p.json()["base_price"] == 1000.0
        assert p.json()["discount"] == 200.0
        assert p.json()["new_price"] == 800.0

        # Booking consumes it.
        day = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
        bk = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": day, "coupon_code": code},
            headers=ha,
        )
        assert bk.status_code == 201, bk.text
        assert bk.json()["service_price"] == 800.0

        # Single use exhausted (fresh slot — only the coupon blocks).
        day2 = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
        bk2 = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": day2, "coupon_code": code},
            headers=ha,
        )
        assert bk2.status_code == 400

    async def test_stranger_cannot_use_selected(self, client, session):
        mh, mp, s, ha, a, hb, b = await self._setup(client, session)

        r = await client.post(
            "/api/v1/admin/coupons",
            json={"kind": "fixed", "value": 300, "user_ids": [a.id]},
            headers=mh,
        )
        assert r.status_code == 201, r.text
        code = r.json()["code"]

        p = await client.post(
            "/api/v1/client/coupons/preview",
            json={"master_id": mp.id, "service_id": s.id, "code": code},
            headers=hb,
        )
        assert p.status_code == 403

    async def test_master_cannot_target_strangers(self, client, session):
        mh, mp, s, ha, a, hb, b = await self._setup(client, session)

        r = await client.post(
            "/api/v1/admin/coupons",
            json={"kind": "percent", "value": 10, "user_ids": [b.id]},
            headers=mh,
        )
        assert r.status_code == 400

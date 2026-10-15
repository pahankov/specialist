"""Service bundles (complexes): CRUD + booking as one appointment."""
from datetime import datetime, timedelta


async def _mk_master(session, email="bundlemaster@example.com",
                     phone="+79990008811"):
    from app.models.user import User, UserRole
    from app.models.master_profile import MasterProfile
    from app.utils.security import hash_password

    u = User(name="Bundle Master", email=email,
             hashed_password=hash_password("SecurePass123!"),
             phone=phone, role=UserRole.MASTER, is_active=True)
    session.add(u)
    await session.flush()
    mp = MasterProfile(user_id=u.id, status="active",
                       work_start_hour=9, work_end_hour=18)
    session.add(mp)
    await session.flush()
    await session.commit()
    return u, mp


async def _mk_services(session, mp, defs=(("Cut", 60, 1000), ("Color", 90, 2000))):
    from app.models.service import Service

    out = []
    for name, dur, price in defs:
        s = Service(master_id=mp.id, name=name, duration_minutes=dur,
                    price=price, is_active=True)
        session.add(s)
        out.append(s)
    await session.commit()
    return out


async def _client_headers(session, email="bundlecab@example.com",
                          phone="+79990008822"):
    from app.models.user import User, UserRole
    from app.utils.security import hash_password
    from app.modules.auth.token import create_access_token

    u = User(name="Bundle Cab", email=email,
             hashed_password=hash_password("SecurePass123!"),
             phone=phone, role=UserRole.CLIENT, is_active=True)
    session.add(u)
    await session.commit()
    token = create_access_token({"sub": str(u.id), "role": "CLIENT",
                                 "name": u.name, "is_admin": False})
    return {"Authorization": f"Bearer {token}"}, u


async def _master_headers(session, user):
    from app.modules.auth.token import create_access_token

    token = create_access_token({"sub": str(user.id), "role": "MASTER",
                                 "name": user.name, "is_admin": False})
    return {"Authorization": f"Bearer {token}"}


class TestBundleCrud:
    async def test_create_list_update_delete(self, client, session):
        user, mp = await _mk_master(session)
        s1, s2 = await _mk_services(session, mp)
        h = await _master_headers(session, user)

        r = await client.post(
            "/api/v1/admin/bundles",
            json={"name": "Full set", "service_ids": [s1.id, s2.id]},
            headers=h,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["duration_total"] == 150
        assert body["price_total"] == 3000
        assert body["effective_price"] == 3000
        assert [s["name"] for s in body["services"]] == ["Cut", "Color"]
        bid = body["id"]

        lst = await client.get("/api/v1/admin/bundles", headers=h)
        assert lst.status_code == 200
        assert any(b["id"] == bid for b in lst.json())

        # Custom price overrides the sum.
        up = await client.patch(
            f"/api/v1/admin/bundles/{bid}", json={"price": 2500}, headers=h)
        assert up.status_code == 200, up.text
        assert up.json()["effective_price"] == 2500
        assert up.json()["price_total"] == 3000

        d = await client.delete(f"/api/v1/admin/bundles/{bid}", headers=h)
        assert d.status_code == 204
        lst2 = await client.get("/api/v1/admin/bundles", headers=h)
        assert all(b["id"] != bid for b in lst2.json())

    async def test_create_rejects_single_service(self, client, session):
        user, mp = await _mk_master(session)
        (s1,) = await _mk_services(session, mp, (("Solo", 30, 500),))
        h = await _master_headers(session, user)
        r = await client.post(
            "/api/v1/admin/bundles",
            json={"name": "Solo?", "service_ids": [s1.id]},
            headers=h,
        )
        assert r.status_code == 422

    async def test_create_rejects_foreign_service(self, client, session):
        user, mp = await _mk_master(session)
        await _mk_services(session, mp)
        _, mp2 = await _mk_master(session, email="bundleother@example.com",
                                  phone="+79990008813")
        (foreign,) = await _mk_services(session, mp2, (("Alien", 30, 500),))
        h = await _master_headers(session, user)
        r = await client.post(
            "/api/v1/admin/bundles",
            json={"name": "Steal", "service_ids": [foreign.id, foreign.id]},
            headers=h,
        )
        # Dupes collapse to one id; one id is not own → 404 either way.
        assert r.status_code in (404, 422)

    async def test_cannot_touch_foreign_bundle(self, client, session):
        user, mp = await _mk_master(session)
        s1, s2 = await _mk_services(session, mp)
        h = await _master_headers(session, user)
        r = await client.post(
            "/api/v1/admin/bundles",
            json={"name": "Mine", "service_ids": [s1.id, s2.id]},
            headers=h,
        )
        bid = r.json()["id"]

        user2, _ = await _mk_master(session, email="bundleother2@example.com",
                                    phone="+79990008814")
        h2 = await _master_headers(session, user2)
        assert (await client.patch(
            f"/api/v1/admin/bundles/{bid}", json={"name": "Hijack"},
            headers=h2)).status_code == 404
        lst = await client.get("/api/v1/admin/bundles", headers=h2)
        assert all(b["id"] != bid for b in lst.json())


class TestBundleBooking:
    async def _setup(self, client, session):
        user, mp = await _mk_master(session)
        s1, s2 = await _mk_services(session, mp)
        h = await _master_headers(session, user)
        r = await client.post(
            "/api/v1/admin/bundles",
            json={"name": "Set", "service_ids": [s1.id, s2.id], "price": 2500},
            headers=h,
        )
        assert r.status_code == 201, r.text
        ch, _ = await _client_headers(session)
        return mp, r.json(), ch, h

    def _day(self, days=3, hour=10):
        return (datetime.now() + timedelta(days=days)).replace(
            hour=hour, minute=0, second=0, microsecond=0)

    async def test_book_bundle_and_conflict(self, client, session):
        from app.models.appointment import Appointment
        from app.models.notification import Notification
        from app.models.service import Service
        from sqlalchemy import select

        mp, bundle, ch, _ = await self._setup(client, session)
        day = self._day()

        r = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "bundle_id": bundle["id"],
                  "appointment_date": day.isoformat()},
            headers=ch,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["status"] == "pending"
        assert body["service_id"] is None
        assert body["bundle_id"] == bundle["id"]
        assert body["service_name"] == "Set"
        assert float(body["service_price"]) == 2500
        appt_id = body["id"]

        # Snapshot columns persisted.
        row = (await session.execute(
            select(Appointment).where(Appointment.id == appt_id)
        )).scalar_one()
        assert row.duration_minutes == 150
        assert float(row.price) == 2500

        # Master got the bell with the bundle name.
        notes = (await session.execute(
            select(Notification).where(Notification.audience == "booking")
        )).scalars().all()
        assert any("Set" in n.text for n in notes)

        # 150-min bundle at 10:00 blocks a service booking at 12:00.
        s = (await session.execute(select(Service))).scalars().first()
        clash = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": s.id,
                  "appointment_date": self._day(hour=12).isoformat()},
            headers=ch,
        )
        assert clash.status_code == 409

    async def test_book_requires_exactly_one(self, client, session):
        mp, bundle, ch, _ = await self._setup(client, session)
        day = self._day().isoformat()
        both = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "service_id": 1,
                  "bundle_id": bundle["id"], "appointment_date": day},
            headers=ch,
        )
        assert both.status_code == 400
        neither = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "appointment_date": day},
            headers=ch,
        )
        assert neither.status_code in (400, 422)

    async def test_bundle_lists_and_stats(self, client, session):
        mp, bundle, ch, mh = await self._setup(client, session)

        bl = await client.get("/api/v1/client/bundles",
                              params={"master_id": mp.id}, headers=ch)
        assert bl.status_code == 200, bl.text
        items = bl.json()
        assert len(items) == 1
        assert items[0]["duration_total"] == 150
        assert items[0]["effective_price"] == 2500

        day = self._day()
        r = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "bundle_id": bundle["id"],
                  "appointment_date": day.isoformat()},
            headers=ch,
        )
        appt_id = r.json()["id"]

        # Complete it as the master, then revenue counts the bundle price.
        c = await client.patch(f"/api/v1/admin/appointments/{appt_id}/complete",
                               headers=mh)
        assert c.status_code == 200, c.text

        st = await client.get("/api/v1/client/stats", headers=ch)
        assert st.status_code == 200, st.text
        assert st.json()["total_spent"] == 2500
        assert st.json()["completed_visits"] == 1

        mine = await client.get("/api/v1/client/appointments", headers=ch)
        assert any(a["bundle_id"] == bundle["id"] and a["service_name"] == "Set"
                   for a in mine.json())

    async def test_duration_overrides(self, client, session):
        user, mp = await _mk_master(session)
        s1, s2 = await _mk_services(session, mp)
        h = await _master_headers(session, user)

        r = await client.post(
            "/api/v1/admin/bundles",
            json={"name": "Express", "service_ids": [s1.id, s2.id],
                  "durations": {str(s1.id): 30}},
            headers=h,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        # 30 (override) + 90 (own) = 120, not 150.
        assert body["duration_total"] == 120
        assert body["services"][0]["duration_minutes"] == 30
        assert body["services"][0]["base_duration_minutes"] == 60

        # Booking uses the overridden total.
        ch, _ = await _client_headers(session)
        day = self._day()
        b = await client.post(
            "/api/v1/client/appointments",
            json={"master_id": mp.id, "bundle_id": body["id"],
                  "appointment_date": day.isoformat()},
            headers=ch,
        )
        assert b.status_code == 201, b.text
        assert b.json()["service_name"] == "Express"

        # Override outside the complex is rejected.
        bad = await client.post(
            "/api/v1/admin/bundles",
            json={"name": "Bad", "service_ids": [s1.id, s2.id],
                  "durations": {"999999": 30}},
            headers=h,
        )
        assert bad.status_code == 400


class TestAdminBundleBooking:
    async def test_admin_books_bundle(self, client, session):
        from datetime import timedelta
        user, mp = await _mk_master(session)
        s1, s2 = await _mk_services(session, mp)
        h = await _master_headers(session, user)
        ch, cu = await _client_headers(session)

        b = await client.post(
            '/api/v1/admin/bundles',
            json={'name': 'Full set', 'service_ids': [s1.id, s2.id]},
            headers=h,
        )
        assert b.status_code == 201, b.text
        bid = b.json()['id']
        day = (__import__('datetime').datetime.now() +
               timedelta(days=3)).isoformat()

        r = await client.post(
            '/api/v1/admin/appointments/book',
            json={'client_id': cu.id, 'bundle_id': bid,
                  'appointment_date': day, 'status': 'confirmed'},
            headers=h,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body['bundle_id'] == bid
        assert body['service_id'] is None

        # Exactly one of service/bundle — both or neither is 400.
        bad = await client.post(
            '/api/v1/admin/appointments/book',
            json={'client_id': cu.id, 'service_id': s1.id,
                  'bundle_id': bid, 'appointment_date': day},
            headers=h,
        )
        assert bad.status_code == 400
        bad2 = await client.post(
            '/api/v1/admin/appointments/book',
            json={'client_id': cu.id, 'appointment_date': day},
            headers=h,
        )
        assert bad2.status_code in (400, 422)


class TestBundleDurationOverride:
    async def test_override_wins_over_sum(self, client, session):
        user, mp = await _mk_master(session)
        s1, s2 = await _mk_services(session, mp)
        h = await _master_headers(session, user)

        r = await client.post(
            '/api/v1/admin/bundles',
            json={'name': 'Fast set', 'service_ids': [s1.id, s2.id],
                  'duration_override': 90},
            headers=h,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body['duration_total'] == 90
        assert body['duration_override'] == 90

        # Booking spans the override, not the 150-min sum.
        ch, _ = await _client_headers(session)
        day = (datetime.now() + timedelta(days=3)).isoformat()
        b = await client.post(
            '/api/v1/client/appointments',
            json={'master_id': mp.id, 'bundle_id': body['id'],
                  'appointment_date': day},
            headers=ch,
        )
        assert b.status_code == 201, b.text

        # Out-of-range override rejected.
        bad = await client.post(
            '/api/v1/admin/bundles',
            json={'name': 'Bad', 'service_ids': [s1.id, s2.id],
                  'duration_override': 3},
            headers=h,
        )
        assert bad.status_code == 400


class TestDiscounts:
    async def test_pricing_math(self):
        from app.services.pricing import apply_discount, clamp_discount

        assert apply_discount(1000, 20) == 800.0
        assert apply_discount(1000, 0) == 1000.0
        assert apply_discount(1000, None) == 1000.0
        assert apply_discount(999, 33) == round(999 * 0.67, 2)
        assert clamp_discount(91) == 90
        assert clamp_discount(-5) == 0

    async def test_service_discount_flows_to_booking(self, client, session):
        user, mp = await _mk_master(session)
        h = await _master_headers(session, user)
        s = await client.post(
            '/api/v1/admin/services',
            json={'name': 'Cut', 'duration_minutes': 60, 'price': 1000,
                  'discount_percent': 25},
            headers=h,
        )
        assert s.status_code == 201, s.text
        assert s.json()['discount_percent'] == 25
        assert s.json()['effective_price'] == 750.0

        ch, _ = await _client_headers(session)
        day = (datetime.now() + timedelta(days=3)).isoformat()
        b = await client.post(
            '/api/v1/client/appointments',
            json={'master_id': mp.id, 'service_id': s.json()['id'],
                  'appointment_date': day},
            headers=ch,
        )
        assert b.status_code == 201, b.text
        assert b.json()['service_price'] == 750.0

        # Over-90 rejected.
        bad = await client.post(
            '/api/v1/admin/services',
            json={'name': 'Bad', 'duration_minutes': 60, 'price': 1000,
                  'discount_percent': 91},
            headers=h,
        )
        assert bad.status_code == 422

    async def test_bundle_discount(self, client, session):
        user, mp = await _mk_master(session)
        s1, s2 = await _mk_services(session, mp)
        h = await _master_headers(session, user)

        r = await client.post(
            '/api/v1/admin/bundles',
            json={'name': 'Sale set', 'service_ids': [s1.id, s2.id],
                  'price': 2000, 'discount_percent': 10},
            headers=h,
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body['discount_percent'] == 10
        assert body['effective_price'] == 1800.0

        ch, _ = await _client_headers(session)
        day = (datetime.now() + timedelta(days=3)).isoformat()
        b = await client.post(
            '/api/v1/client/appointments',
            json={'master_id': mp.id, 'bundle_id': body['id'],
                  'appointment_date': day},
            headers=ch,
        )
        assert b.status_code == 201, b.text
        assert b.json()['service_price'] == 1800.0

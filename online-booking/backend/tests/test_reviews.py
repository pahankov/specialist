"""Tests for admin reviews API."""
from datetime import datetime, timezone


class TestGetAdminReviews:
    """Tests for GET /api/v1/admin/reviews"""

    async def test_get_reviews_empty(self, client, super_admin_headers):
        """Returns empty paginated response when no reviews."""
        resp = await client.get("/api/v1/admin/reviews", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert data["total"] == 0

    async def test_get_reviews_with_data(self, client, super_admin_headers, session, created_master_id):
        """Returns reviews for master."""
        from app.models.review import Review
        from app.models.service import Service
        from app.models.client_profile import ClientProfile
        from app.models.user import User

        # Create service
        service = Service(
            master_id=created_master_id,
            name="Test Service",
            duration_minutes=60,
            price=2500,
            is_active=True,
        )
        session.add(service)
        await session.flush()

        # Create client user + profile
        client_user = User(
            name="Test Client",
            email="client_review@example.com",
            phone="+79001234567",
            role="CLIENT",
        )
        session.add(client_user)
        await session.flush()

        client_profile = ClientProfile(user_id=client_user.id)
        session.add(client_profile)
        await session.flush()

        # Create review
        review = Review(
            appointment_id=1,  # dummy
            master_id=created_master_id,
            client_name="Test Client",
            client_phone="+79001234567",
            rating=5.0,
            comment="Отличный мастер!",
            is_published=True,
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)

        resp = await client.get("/api/v1/admin/reviews", headers=super_admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        assert len(data["items"]) >= 1
        assert data["items"][0]["rating"] == 5.0

    async def test_filter_reviews_by_master_id(self, client, super_admin_headers, session, created_master_id):
        """Filter reviews by master_id."""
        from app.models.review import Review

        review = Review(
            appointment_id=1,
            master_id=created_master_id,
            client_name="Test",
            client_phone="+79001234567",
            rating=4.0,
            comment="Test",
            is_published=True,
        )
        session.add(review)
        await session.commit()

        resp = await client.get(
            "/api/v1/admin/reviews",
            params={"master_id": created_master_id},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1

    async def test_filter_reviews_by_published_status(self, client, super_admin_headers, session, created_master_id):
        """Filter reviews by published status."""
        from app.models.review import Review

        review = Review(
            appointment_id=1,
            master_id=created_master_id,
            client_name="Test",
            client_phone="+79001234567",
            rating=3.0,
            comment="Test",
            is_published=False,
        )
        session.add(review)
        await session.commit()

        resp = await client.get(
            "/api/v1/admin/reviews",
            params={"is_published": False},
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["is_published"] is False


class TestGetAverageRating:
    """Tests for GET /api/v1/admin/reviews/average/{master_id}"""

    async def test_average_rating_with_reviews(self, client, super_admin_headers, session, created_master_id):
        """Returns correct average rating."""
        from app.models.review import Review

        review = Review(
            appointment_id=1,
            master_id=created_master_id,
            client_name="Test",
            client_phone="+79001234567",
            rating=5.0,
            comment="Great!",
            is_published=True,
        )
        session.add(review)
        await session.commit()

        resp = await client.get(
            f"/api/v1/admin/reviews/average/{created_master_id}",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "average_rating" in data
        assert "review_count" in data
        assert data["review_count"] >= 1

    async def test_average_rating_no_reviews(self, client, super_admin_headers):
        """Returns zero when no reviews."""
        resp = await client.get(
            "/api/v1/admin/reviews/average/99999",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["review_count"] == 0
        assert data["average_rating"] is None


class TestPublishReview:
    """Tests for PATCH /api/v1/admin/reviews/{id}/publish"""

    async def test_publish_review(self, client, super_admin_headers, session, created_master_id):
        """Superadmin can publish a review."""
        from app.models.review import Review

        review = Review(
            appointment_id=1,
            master_id=created_master_id,
            client_name="Test",
            client_phone="+79001234567",
            rating=4.0,
            comment="Test",
            is_published=False,
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)

        resp = await client.patch(
            f"/api/v1/admin/reviews/{review.id}/publish",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_published"] is True

    async def test_publish_review_not_found(self, client, super_admin_headers):
        """Returns 404 for non-existent review."""
        resp = await client.patch(
            "/api/v1/admin/reviews/99999/publish",
            headers=super_admin_headers
        )
        assert resp.status_code == 404


class TestUnpublishReview:
    """Tests for PATCH /api/v1/admin/reviews/{id}/unpublish"""

    async def test_unpublish_review(self, client, super_admin_headers, session, created_master_id):
        """Superadmin can unpublish a review."""
        from app.models.review import Review

        review = Review(
            appointment_id=1,
            master_id=created_master_id,
            client_name="Test",
            client_phone="+79001234567",
            rating=5.0,
            comment="Test",
            is_published=True,
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)

        resp = await client.patch(
            f"/api/v1/admin/reviews/{review.id}/unpublish",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_published"] is False

    async def test_unpublish_review_not_found(self, client, super_admin_headers):
        """Returns 404 for non-existent review."""
        resp = await client.patch(
            "/api/v1/admin/reviews/99999/unpublish",
            headers=super_admin_headers
        )
        assert resp.status_code == 404


class TestClientReviews:
    """POST /api/v1/client/reviews — rate own completed visits."""

    async def _setup(self, client, session):
        from datetime import datetime, timedelta
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token

        m = User(name="RevMaster", email="revmaster@example.com",
                 hashed_password=hash_password("SecurePass123!"),
                 phone="+79990009101", role=UserRole.MASTER, is_active=True)
        session.add(m)
        await session.flush()
        session.add(MasterProfile(user_id=m.id, status="active"))
        await session.flush()
        mp = (await session.execute(
            __import__("sqlalchemy").select(MasterProfile).where(
                MasterProfile.user_id == m.id))).scalar_one()
        s = Service(master_id=mp.id, name="RevCut", duration_minutes=60,
                    price=1000, is_active=True)
        session.add(s)

        async def mk_client(name, email, phone):
            u = User(name=name, email=email,
                     hashed_password=hash_password("SecurePass123!"),
                     phone=phone, role=UserRole.CLIENT, is_active=True)
            session.add(u)
            await session.commit()
            token = create_access_token({"sub": str(u.id), "role": "CLIENT",
                                         "name": u.name, "is_admin": False})
            return {"Authorization": f"Bearer {token}"}, u

        ha, _ = await mk_client("RevA", "reva@example.com", "+79990009102")
        hb, _ = await mk_client("RevB", "revb@example.com", "+79990009103")

        day = (datetime.now() + timedelta(days=3)).replace(
            hour=10, minute=0, second=0, microsecond=0).isoformat()

        async def book(headers):
            r = await client.post(
                "/api/v1/client/appointments",
                json={"master_id": mp.id, "service_id": s.id,
                      "appointment_date": day},
                headers=headers,
            )
            assert r.status_code == 201, r.text
            return r.json()["id"]

        mtok = create_access_token({"sub": str(m.id), "role": "MASTER",
                                    "name": m.name, "is_admin": False})
        mh = {"Authorization": f"Bearer {mtok}"}
        return mp, ha, hb, mh, book

    async def test_rate_completed_ok(self, client, session):
        mp, ha, hb, mh, book = await self._setup(client, session)
        appt = await book(ha)
        c = await client.patch(f"/api/v1/admin/appointments/{appt}/confirm", headers=mh)
        assert c.status_code == 200, c.text
        c = await client.patch(f"/api/v1/admin/appointments/{appt}/complete", headers=mh)
        assert c.status_code == 200, c.text

        r = await client.post("/api/v1/client/reviews",
                              json={"appointment_id": appt, "rating": 5,
                                    "comment": "Great"},
                              headers=ha)
        assert r.status_code == 201, r.text
        assert r.json()["rating"] == 5

        # Duplicate → 409.
        d = await client.post("/api/v1/client/reviews",
                              json={"appointment_id": appt, "rating": 4},
                              headers=ha)
        assert d.status_code == 409

        # Average reflects the new review.
        avg = await client.get("/api/v1/reviews/average",
                               params={"master_id": mp.id})
        assert avg.json()["average_rating"] == 5.0

        # Mine lists it.
        mine = await client.get("/api/v1/client/reviews/mine", headers=ha)
        assert [x["appointment_id"] for x in mine.json()] == [appt]

    async def test_rate_pending_rejected(self, client, session):
        _, ha, __, ___, book = await self._setup(client, session)
        appt = await book(ha)
        r = await client.post("/api/v1/client/reviews",
                              json={"appointment_id": appt, "rating": 5},
                              headers=ha)
        assert r.status_code == 400

    async def test_rate_stranger_rejected(self, client, session):
        _, ha, hb, mh, book = await self._setup(client, session)
        appt = await book(ha)
        await client.patch(f"/api/v1/admin/appointments/{appt}/confirm", headers=mh)
        await client.patch(f"/api/v1/admin/appointments/{appt}/complete", headers=mh)
        r = await client.post("/api/v1/client/reviews",
                              json={"appointment_id": appt, "rating": 1},
                              headers=hb)
        assert r.status_code == 403


class TestAutoComplete:
    """Auto-complete switch + background sweep."""

    async def _setup(self, session):
        from datetime import datetime, timedelta, timezone
        from sqlalchemy import select
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        m = User(name="ACMaster", email="acmaster@example.com",
                 hashed_password=hash_password("SecurePass123!"),
                 phone="+79990009201", role=UserRole.MASTER, is_active=True)
        session.add(m)
        await session.flush()
        mp = MasterProfile(user_id=m.id, status="active", auto_complete=True)
        session.add(mp)
        await session.flush()
        s = Service(master_id=mp.id, name="ACCut", duration_minutes=60,
                    price=1000, is_active=True)
        session.add(s)
        await session.flush()
        c = User(name="ACC", email="acc@example.com",
                 hashed_password=hash_password("SecurePass123!"),
                 phone="+79990009202", role=UserRole.CLIENT, is_active=True)
        session.add(c)
        await session.flush()
        cp = ClientProfile(user_id=c.id)
        session.add(cp)
        await session.flush()

        past = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=4)
        old = Appointment(master_id=mp.id, service_id=s.id, client_id=cp.id,
                          duration_minutes=60, appointment_date=past,
                          status="confirmed")
        future = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=1)
        upcoming = Appointment(master_id=mp.id, service_id=s.id, client_id=cp.id,
                               duration_minutes=60, appointment_date=future,
                               status="confirmed")
        pending_past = Appointment(master_id=mp.id, service_id=s.id, client_id=cp.id,
                                   duration_minutes=60, appointment_date=past,
                                   status="pending")
        session.add_all([old, upcoming, pending_past])
        await session.commit()
        return mp, old, upcoming, pending_past, c

    async def test_sweep_completes_only_past_confirmed(self, client, session):
        from sqlalchemy import select
        from app.models.appointment import Appointment
        from app.models.notification import Notification
        from app.services.auto_complete import run_auto_complete_once

        mp, old, upcoming, pending_past, c = await self._setup(session)

        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
        factory = async_sessionmaker(session.bind, class_=AsyncSession,
                                     expire_on_commit=False)
        done = await run_auto_complete_once(session_factory=factory)
        assert done == 1

        await session.refresh(old)
        await session.refresh(upcoming)
        await session.refresh(pending_past)
        assert old.status == "completed"
        assert upcoming.status == "confirmed"
        assert pending_past.status == "pending"

        bells = (await session.execute(
            select(Notification).where(Notification.recipient_id == c.id)
        )).scalars().all()
        assert any("завершена" in (b.text or "") for b in bells)

    async def test_sweep_respects_switch_off(self, client, session):
        from app.services.auto_complete import run_auto_complete_once
        from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

        mp, old, __, ___, ____ = await self._setup(session)
        mp.auto_complete = False
        await session.commit()

        factory = async_sessionmaker(session.bind, class_=AsyncSession,
                                     expire_on_commit=False)
        done = await run_auto_complete_once(session_factory=factory)
        assert done == 0
        await session.refresh(old)
        assert old.status == "confirmed"

    async def test_profile_toggle_roundtrip(self, client, session):
        from app.modules.auth.token import create_access_token
        from app.models.master_profile import MasterProfile
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        m = User(name="ACT", email="act@example.com",
                 hashed_password=hash_password("SecurePass123!"),
                 phone="+79990009203", role=UserRole.MASTER, is_active=True)
        session.add(m)
        await session.flush()
        session.add(MasterProfile(user_id=m.id, status="active"))
        await session.commit()
        tok = create_access_token({"sub": str(m.id), "role": "MASTER",
                                   "name": m.name, "is_admin": False})
        h = {"Authorization": f"Bearer {tok}"}

        g = await client.get("/api/v1/admin/profile", headers=h)
        assert g.status_code == 200, g.text
        assert g.json()["auto_complete"] is False

        p = await client.patch("/api/v1/admin/profile",
                               json={"auto_complete": True}, headers=h)
        assert p.status_code == 200, p.text
        g2 = await client.get("/api/v1/admin/profile", headers=h)
        assert g2.json()["auto_complete"] is True


class TestDeleteReview:
    """Tests for DELETE /api/v1/admin/reviews/{id}"""

    async def test_delete_review(self, client, super_admin_headers, session, created_master_id):
        """Superadmin can delete a review."""
        from app.models.review import Review

        review = Review(
            appointment_id=1,
            master_id=created_master_id,
            client_name="Test",
            client_phone="+79001234567",
            rating=3.0,
            comment="Test",
            is_published=True,
        )
        session.add(review)
        await session.commit()
        await session.refresh(review)

        resp = await client.delete(
            f"/api/v1/admin/reviews/{review.id}",
            headers=super_admin_headers
        )
        assert resp.status_code == 204

        # Verify deleted
        resp = await client.get("/api/v1/admin/reviews", headers=super_admin_headers)
        data = resp.json()
        assert not any(r["id"] == review.id for r in data["items"])

    async def test_delete_review_not_found(self, client, super_admin_headers):
        """Returns 404 for non-existent review."""
        resp = await client.delete(
            "/api/v1/admin/reviews/99999",
            headers=super_admin_headers
        )
        assert resp.status_code == 404

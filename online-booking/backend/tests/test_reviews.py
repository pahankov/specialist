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

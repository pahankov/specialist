"""Tests for master statistics endpoints."""
from datetime import datetime, timedelta


class TestGetMasterStats:
    """Tests for GET /api/v1/admin/masters/{id}/stats"""

    async def test_get_stats_master_not_found(self, client, super_admin_headers):
        """Returns 404 for non-existent master."""
        resp = await client.get(
            "/api/v1/admin/masters/99999/stats",
            headers=super_admin_headers
        )
        assert resp.status_code == 404

    async def test_get_stats_empty_master(self, client, super_admin_headers, session, created_master_id):
        """Returns stats with zero counts for master with no data."""
        resp = await client.get(
            f"/api/v1/admin/masters/{created_master_id}/stats",
            headers=super_admin_headers
        )
        assert resp.status_code == 200, f"Stats failed: {resp.text}"
        data = resp.json()
        assert data["master_id"] == created_master_id
        assert data["total_appointments"] == 0
        assert data["total_clients"] == 0
        assert data["total_services"] == 0
        assert data["total_revenue"] == 0.0
        assert data["status_counts"] == {}


class TestGetMasterFull:
    """Tests for GET /api/v1/admin/masters/{id}/full"""

    async def test_get_full_master_not_found(self, client, super_admin_headers):
        """Returns 404 for non-existent master."""
        resp = await client.get(
            "/api/v1/admin/masters/99999/full",
            headers=super_admin_headers
        )
        assert resp.status_code == 404

    async def test_get_full_master_empty(self, client, super_admin_headers, session, created_master_id):
        """Returns full profile with zero stats for master with no data."""
        resp = await client.get(
            f"/api/v1/admin/masters/{created_master_id}/full",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == created_master_id
        assert data["name"] == "Test Master"
        assert data["stats"]["total_appointments"] == 0
        assert data["stats"]["avg_rating"] is None
        assert data["stats"]["review_count"] == 0
        assert data["recent_reviews"] == []
        assert data["recent_appointments"] == []

    async def test_get_full_master_with_data(self, client, super_admin_headers, session, created_master_id):
        """Returns full profile with populated stats."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.models.appointment import Appointment
        from app.models.client_profile import ClientProfile
        from app.models.review import Review
        from app.modules.auth.service import hash_password

        # Create a service
        service = Service(
            master_id=created_master_id,
            name="Haircut",
            duration_minutes=60,
            price=2500,
            is_active=True,
        )
        session.add(service)
        await session.flush()
        service_id = service.id

        # Create a client user + profile
        client_user = User(
            name="Client One",
            email="client1@example.com",
            phone="+79001111111",
            role=UserRole.CLIENT,
        )
        session.add(client_user)
        await session.flush()
        client_profile = ClientProfile(user_id=client_user.id)
        session.add(client_profile)
        await session.flush()

        # Create a completed appointment
        appointment = Appointment(
            master_id=created_master_id,
            service_id=service_id,
            client_id=client_profile.id,
            appointment_date=datetime.now() - timedelta(days=2),
            status="completed",
        )
        session.add(appointment)
        await session.flush()

        # Create a review
        review = Review(
            appointment_id=appointment.id,
            master_id=created_master_id,
            client_name="Client One",
            client_phone="+79001111111",
            rating=5.0,
            comment="Great!",
            is_published=True,
        )
        session.add(review)
        await session.flush()

        # Get full profile
        resp = await client.get(
            f"/api/v1/admin/masters/{created_master_id}/full",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()

        # Verify stats
        assert data["stats"]["total_appointments"] >= 1
        assert data["stats"]["total_clients"] >= 1
        assert data["stats"]["total_services"] >= 1
        assert data["stats"]["total_revenue"] >= 2500.0
        assert data["stats"]["avg_rating"] == 5.0
        assert data["stats"]["review_count"] >= 1

        # Verify recent data
        assert len(data["recent_reviews"]) >= 1
        assert len(data["recent_appointments"]) >= 1
        assert data["recent_reviews"][0]["rating"] == 5.0
        assert data["recent_appointments"][0]["status"] == "completed"


class TestMasterStatsWithMixedStatus:
    """Tests for stats with multiple appointment statuses."""

    async def test_status_counts_with_multiple_statuses(
        self, client, super_admin_headers, session, created_master_id
    ):
        """Correctly counts appointments by status."""
        from app.models.appointment import Appointment

        # Create appointments with different statuses
        statuses = ["pending", "confirmed", "completed", "cancelled"]
        for i, status in enumerate(statuses):
            appt = Appointment(
                master_id=created_master_id,
                service_id=1,
                client_id=1,
                appointment_date=datetime.now() + timedelta(days=i),
                status=status,
            )
            session.add(appt)
        await session.flush()

        resp = await client.get(
            f"/api/v1/admin/masters/{created_master_id}/stats",
            headers=super_admin_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_appointments"] >= 4
        assert data["status_counts"]["pending"] >= 1
        assert data["status_counts"]["confirmed"] >= 1
        assert data["status_counts"]["completed"] >= 1
        assert data["status_counts"]["cancelled"] >= 1

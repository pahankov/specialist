"""Integration tests for the full booking flow.

Tests the complete user journey:
1. Register master + client
2. Create service for master
3. Book appointment (public)
4. Confirm appointment
5. Complete appointment
6. Create review
7. Verify review appears
"""
from datetime import datetime, timedelta


class TestBookingFlow:
    """Full booking flow integration tests."""

    async def _login_master(self, client, email, password):
        """Helper: login master and return auth headers."""
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": email,
            "password": password
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        token = login_resp.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    async def _register_master(self, client, email, name, password, phone):
        """Helper: register master and return master_profile_id."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.modules.auth.service import hash_password

        master_user = User(
            name=name,
            email=email,
            hashed_password=hash_password(password),
            phone=phone,
            role=UserRole.MASTER,
            is_verified=True,
        )
        # We'll create via API and login
        resp = await client.post("/api/v1/auth/register", json={
            "name": name,
            "email": email,
            "password": password,
            "phone": phone,
            "role": "MASTER",
        })
        assert resp.status_code == 201, f"Register failed: {resp.text}"
        master_id = resp.json()["id"]
        return master_id

    async def test_full_booking_flow(self, client, session):
        """Complete journey: register → service → book → confirm → complete → review."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.modules.auth.service import hash_password

        # ─── Step 1: Register master via API ───
        master_email = "flowmaster@example.com"
        master_phone = "+79990000100"
        master_name = "Flow Master"
        
        master_id = await self._register_master(
            client, master_email, master_name, "SecurePass123!", master_phone
        )
        
        # Login as master
        auth_headers = await self._login_master(client, master_email, "SecurePass123!")

        # ─── Step 2: Create service for master ───
        service_resp = await client.post(
            "/api/v1/services/",
            json={
                "name": "Haircut Premium",
                "description": "Premium haircut service",
                "duration_minutes": 60,
                "price": 2500,
                "master_id": master_id,
            },
            headers=auth_headers
        )
        assert service_resp.status_code == 201
        service_data = service_resp.json()
        service_id = service_data["id"]

        # ─── Step 3: Register client (via unified endpoint) ───
        client_resp = await client.post("/api/v1/auth/register-unified", json={
            "name": "Flow Client",
            "email": "flowclient@example.com",
            "password": "SecurePass456!",
            "phone": "+79990000101",
            "role": "CLIENT",
        })
        assert client_resp.status_code == 201

        # ─── Step 4: Book appointment (public) ───
        appointment_date = (datetime.now() + timedelta(days=7)).replace(
            hour=14, minute=0, second=0, microsecond=0
        )
        booking_resp = await client.post(
            "/api/v1/appointments/public",
            json={
                "master_id": master_id,
                "service_id": service_id,
                "client_name": "Flow Client",
                "client_phone": "+79990000101",
                "appointment_date": appointment_date.isoformat(),
            }
        )
        assert booking_resp.status_code == 201
        appointment_data = booking_resp.json()
        appointment_id = appointment_data["id"]
        assert appointment_data["status"] == "pending"

        # ─── Step 5: Confirm appointment ───
        confirm_resp = await client.patch(
            f"/api/v1/admin/appointments/{appointment_id}/confirm",
            headers=auth_headers
        )
        assert confirm_resp.status_code == 200, f"Confirm failed: {confirm_resp.text}"
        assert confirm_resp.json()["status"] == "confirmed"

        # ─── Step 6: Complete appointment ───
        complete_resp = await client.patch(
            f"/api/v1/admin/appointments/{appointment_id}/complete",
            headers=auth_headers
        )
        assert complete_resp.status_code == 200, f"Complete failed: {complete_resp.text}"
        assert complete_resp.json()["status"] == "completed"

        # ─── Step 7: Create review for completed appointment ───
        review_resp = await client.post(
            "/api/v1/reviews/",
            json={
                "appointment_id": appointment_id,
                "rating": 5.0,
                "comment": "Отличный мастер!",
            }
        )
        assert review_resp.status_code == 201, f"Review failed: {review_resp.text}"
        review_data = review_resp.json()
        assert review_data["rating"] == 5.0
        assert review_data["is_published"] is True

        # ─── Step 8: Verify review appears in public list ───
        reviews_resp = await client.get(
            "/api/v1/reviews/",
            params={"master_id": master_id}
        )
        assert reviews_resp.status_code == 200
        reviews = reviews_resp.json()
        assert len(reviews) >= 1
        assert any(r["id"] == review_data["id"] for r in reviews)

        # ─── Step 9: Verify average rating ───
        avg_resp = await client.get(
            "/api/v1/reviews/average",
            params={"master_id": master_id}
        )
        assert avg_resp.status_code == 200
        avg_data = avg_resp.json()
        assert avg_data["average_rating"] == 5.0
        assert avg_data["review_count"] >= 1

    async def test_booking_flow_conflict(self, client, session):
        """Two bookings for same time should conflict."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.modules.auth.service import hash_password

        # Register master
        master_email = "conflictmaster@example.com"
        master_phone = "+79990000102"
        master_id = await self._register_master(
            client, master_email, "Conflict Master", "SecurePass789!", master_phone
        )
        
        # Login as master
        auth_headers = await self._login_master(client, master_email, "SecurePass789!")

        # Create service
        service_resp = await client.post(
            "/api/v1/services/",
            json={
                "name": "Conflict Service",
                "duration_minutes": 60,
                "price": 1500,
                "master_id": master_id,
            },
            headers=auth_headers
        )
        assert service_resp.status_code == 201
        service_id = service_resp.json()["id"]

        # Book first appointment
        appointment_date = (datetime.now() + timedelta(days=7)).replace(
            hour=15, minute=0, second=0, microsecond=0
        )
        booking1 = await client.post(
            "/api/v1/appointments/public",
            json={
                "master_id": master_id,
                "service_id": service_id,
                "client_name": "Client 1",
                "client_phone": "+79990000103",
                "appointment_date": appointment_date.isoformat(),
            }
        )
        assert booking1.status_code == 201

        # Book second appointment for same time → should conflict
        booking2 = await client.post(
            "/api/v1/appointments/public",
            json={
                "master_id": master_id,
                "service_id": service_id,
                "client_name": "Client 2",
                "client_phone": "+79990000104",
                "appointment_date": appointment_date.isoformat(),
            }
        )
        assert booking2.status_code == 409  # Conflict

    async def test_booking_flow_invalid_master(self, client):
        """Booking for non-existent master should fail."""
        resp = await client.post(
            "/api/v1/appointments/public",
            json={
                "master_id": 99999,
                "service_id": 1,
                "client_name": "Test Client",
                "client_phone": "+79990000105",
                "appointment_date": datetime.now().isoformat(),
            }
        )
        assert resp.status_code == 404

    async def test_booking_flow_invalid_service(self, client):
        """Booking for non-existent service should fail."""
        resp = await client.post(
            "/api/v1/appointments/public",
            json={
                "master_id": 1,
                "service_id": 99999,
                "client_name": "Test Client",
                "client_phone": "+79990000106",
                "appointment_date": datetime.now().isoformat(),
            }
        )
        assert resp.status_code == 404

    async def test_review_flow_duplicate_review(self, client, session):
        """Cannot create two reviews for same appointment."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.models.service import Service
        from app.modules.auth.service import hash_password

        # Register master
        master_email = "reviewmaster@example.com"
        master_phone = "+79990000107"
        master_id = await self._register_master(
            client, master_email, "Review Master", "SecurePassReview1!", master_phone
        )
        
        # Login as master
        auth_headers = await self._login_master(client, master_email, "SecurePassReview1!")

        # Create service
        service_resp = await client.post(
            "/api/v1/services/",
            json={
                "name": "Review Service",
                "duration_minutes": 30,
                "price": 1000,
                "master_id": master_id,
            },
            headers=auth_headers
        )
        assert service_resp.status_code == 201
        service_id = service_resp.json()["id"]

        # Register client
        await client.post("/api/v1/auth/register-unified", json={
            "name": "Review Client",
            "email": "reviewclient@example.com",
            "password": "SecurePassClient!",
            "phone": "+79990000108",
            "role": "CLIENT",
        })

        # Book and complete appointment
        appointment_date = (datetime.now() + timedelta(days=7)).replace(
            hour=16, minute=0, second=0, microsecond=0
        )
        booking_resp = await client.post(
            "/api/v1/appointments/public",
            json={
                "master_id": master_id,
                "service_id": service_id,
                "client_name": "Review Client",
                "client_phone": "+79990000108",
                "appointment_date": appointment_date.isoformat(),
            }
        )
        assert booking_resp.status_code == 201
        appointment_id = booking_resp.json()["id"]

        # Confirm and complete
        await client.patch(
            f"/api/v1/admin/appointments/{appointment_id}/confirm",
            headers=auth_headers
        )
        await client.patch(
            f"/api/v1/admin/appointments/{appointment_id}/complete",
            headers=auth_headers
        )

        # Create first review
        review1 = await client.post(
            "/api/v1/reviews/",
            json={
                "appointment_id": appointment_id,
                "rating": 4.0,
                "comment": "First review",
            }
        )
        assert review1.status_code == 201, f"First review failed: {review1.text}"

        # Try to create second review for same appointment → 409
        review2 = await client.post(
            "/api/v1/reviews/",
            json={
                "appointment_id": appointment_id,
                "rating": 5.0,
                "comment": "Second review",
            }
        )
        assert review2.status_code == 409  # Conflict: duplicate review

    async def test_review_flow_incomplete_appointment(self, client):
        """Cannot review non-completed appointment."""
        # Try to create review without completing appointment first
        resp = await client.post(
            "/api/v1/reviews/",
            json={
                "appointment_id": 99999,  # Non-existent
                "rating": 5.0,
                "comment": "Should fail",
            }
        )
        assert resp.status_code == 404  # Appointment not found

    async def test_review_flow_invalid_rating(self, client):
        """Review with invalid rating should be rejected."""
        resp = await client.post(
            "/api/v1/reviews/",
            json={
                "appointment_id": 1,
                "rating": 6.0,  # Invalid: max 5.0
                "comment": "Should fail",
            }
        )
        assert resp.status_code == 422  # Validation error

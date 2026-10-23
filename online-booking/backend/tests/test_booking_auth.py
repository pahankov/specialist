"""Tests for booking module auth guards and available-slots (1.89.0)."""
import pytest
from datetime import datetime, timedelta


class TestAvailableSlotsCustomHours:
    """available-slots must read work_start_hour/work_end_hour from MasterProfile."""

    async def test_available_slots_default_hours(
        self, client, session, created_master_id, test_service_data
    ):
        """Master with default hours (8-22) returns slots from 08:00."""
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from app.modules.auth.token import create_access_token
        from app.models.service import Service

        # Get the master user and create auth token
        from sqlalchemy import select
        user = (await session.execute(
            select(User).join(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        # Create a service via API (authenticated)
        service_resp = await client.post(
            "/api/v1/services/",
            json=test_service_data,
            headers=headers,
        )
        assert service_resp.status_code == 201
        service_id = service_resp.json()["id"]

        tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
        resp = await client.get(
            "/api/v1/appointments/available-slots",
            params={"master_id": created_master_id, "service_id": service_id, "date": tomorrow}
        )
        assert resp.status_code == 200
        slots = resp.json()
        assert len(slots) > 0
        # Default work_start_hour = 8
        first_start = slots[0]["start"]
        assert "08:00" in first_start

    async def test_available_slots_custom_hours(
        self, client, session, created_master_id, test_service_data
    ):
        """Master with custom hours (9-17) returns slots from 09:00."""
        from app.models.master_profile import MasterProfile
        from app.models.user import User, UserRole
        from app.modules.auth.token import create_access_token
        from sqlalchemy import select

        # Set custom work hours on the master profile
        master = (await session.execute(
            select(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()
        master.work_start_hour = 9
        master.work_end_hour = 17
        await session.commit()

        # Get user for auth
        user = (await session.execute(
            select(User).join(MasterProfile).where(MasterProfile.id == created_master_id)
        )).scalar_one()

        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        service_resp = await client.post(
            "/api/v1/services/",
            json=test_service_data,
            headers=headers,
        )
        assert service_resp.status_code == 201
        service_id = service_resp.json()["id"]

        tomorrow = (datetime.now() + timedelta(days=1)).date().isoformat()
        resp = await client.get(
            "/api/v1/appointments/available-slots",
            params={"master_id": created_master_id, "service_id": service_id, "date": tomorrow}
        )
        assert resp.status_code == 200
        slots = resp.json()
        assert len(slots) > 0
        # Custom work_start_hour = 9
        first_start = slots[0]["start"]
        assert "09:00" in first_start

    async def test_available_slots_master_not_found(
        self, client, test_service_data
    ):
        """Non-existent master → 404."""
        resp = await client.get(
            "/api/v1/appointments/available-slots",
            params={"master_id": 99999, "service_id": 1, "date": "2099-01-01"}
        )
        assert resp.status_code == 404


class TestBookingAuth:
    """Authenticated booking endpoints must require master token."""

    async def test_get_appointments_no_auth(self, client):
        """GET /api/v1/appointments/ without auth → 401."""
        resp = await client.get("/api/v1/appointments/")
        assert resp.status_code == 401

    async def test_delete_appointment_no_auth(self, client):
        """DELETE /api/v1/appointments/{id} without auth → 401."""
        resp = await client.delete("/api/v1/appointments/99999")
        assert resp.status_code == 401

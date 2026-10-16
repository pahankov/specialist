"""Tests for refresh token flow."""
from datetime import datetime, timedelta, timezone as dt_timezone


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh and POST /api/v1/auth/logout"""

    async def test_refresh_token_success(self, client, test_master_data):
        """Refresh endpoint returns new access token and new refresh token."""
        # Register and login
        await client.post("/api/v1/auth/register", json=test_master_data)
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"],
            "password": test_master_data["password"],
        })
        assert login_resp.status_code == 200
        old_refresh = login_resp.cookies.get("refresh_token")
        assert old_refresh is not None

        # Refresh
        refresh_resp = await client.post("/api/v1/auth/refresh")
        assert refresh_resp.status_code == 200
        new_data = refresh_resp.json()
        assert "access_token" in new_data

        # New refresh token cookie
        new_refresh = refresh_resp.cookies.get("refresh_token")
        assert new_refresh is not None
        assert new_refresh != old_refresh

    async def test_refresh_token_without_cookie(self, client):
        """Refresh fails without refresh token cookie."""
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    async def test_refresh_token_invalid_type(self, client):
        """Refresh fails with access token as refresh token."""
        # Register and login
        await client.post("/api/v1/auth/register", json={
            "name": "Test",
            "email": "invalid_type@example.com",
            "password": "SecurePass123!",
            "phone": "+79990000099",
            "role": "MASTER",
        })
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": "invalid_type@example.com",
            "password": "SecurePass123!",
        })
        # Set access token as refresh cookie
        client.cookies.set("refresh_token", login_resp.json()["access_token"])

        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401

    async def test_refresh_token_reuse_within_grace_rotates(self, client, test_master_data):
        """Immediate reuse of a just-revoked token rotates again (race grace),
        it does NOT 401 — see test_refresh_rotation_race_absorbed."""
        # Register and login
        await client.post("/api/v1/auth/register", json=test_master_data)
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"],
            "password": test_master_data["password"],
        })
        old_refresh = login_resp.cookies.get("refresh_token")
        assert old_refresh is not None

        # First refresh — should succeed
        refresh_resp = await client.post("/api/v1/auth/refresh")
        assert refresh_resp.status_code == 200
        first_new = refresh_resp.cookies.get("refresh_token")
        assert first_new is not None and first_new != old_refresh

        # Immediate reuse — absorbed by the grace window, rotates once more.
        client.cookies.set("refresh_token", old_refresh)
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 200, resp.text
        assert resp.cookies.get("refresh_token") not in (old_refresh, first_new)

    async def test_refresh_rotation_race_absorbed(self, client, test_master_data):
        """Two tabs refreshing at once: the loser reuses the just-revoked
        token within the grace window and still gets a fresh pair (no logout)."""
        await client.post("/api/v1/auth/register", json=test_master_data)
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"],
            "password": test_master_data["password"],
        })
        old_refresh = login_resp.cookies.get("refresh_token")
        assert old_refresh is not None

        first = await client.post("/api/v1/auth/refresh")
        assert first.status_code == 200

        # Loser tab presents the just-revoked token — absorbed, fresh pair.
        client.cookies.set("refresh_token", old_refresh)
        second = await client.post("/api/v1/auth/refresh")
        assert second.status_code == 200, second.text
        assert "access_token" in second.json()

    async def test_refresh_grace_expired_rejected(self, client, session, test_master_data):
        """A revoked token past the grace window stays dead (theft safety)."""
        from sqlalchemy import select, update
        from app.models.refresh_token import RefreshToken

        await client.post("/api/v1/auth/register", json=test_master_data)
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"],
            "password": test_master_data["password"],
        })
        old_refresh = login_resp.cookies.get("refresh_token")
        assert old_refresh is not None

        assert (await client.post("/api/v1/auth/refresh")).status_code == 200

        # Age the revocation beyond the grace window.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token == old_refresh)
            .values(revoked_at=datetime.now(dt_timezone.utc) - timedelta(hours=1))
        )
        await session.commit()

        client.cookies.set("refresh_token", old_refresh)
        resp = await client.post("/api/v1/auth/refresh")
        assert resp.status_code == 401


class TestLogout:
    """Tests for POST /api/v1/auth/logout"""

    async def test_logout_revokes_refresh_token(self, client, test_master_data):
        """Logout revokes the refresh token so it cannot be used for refresh."""
        # Register and login
        await client.post("/api/v1/auth/register", json=test_master_data)
        login_resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"],
            "password": test_master_data["password"],
        })
        old_refresh = login_resp.cookies.get("refresh_token")
        assert old_refresh is not None

        # Logout
        resp = await client.post("/api/v1/auth/logout")
        assert resp.status_code == 200

        # Cookie should be deleted
        assert client.cookies.get("refresh_token") is None

        # Try refresh with old token — should fail
        client.cookies.set("refresh_token", old_refresh)
        refresh_resp = await client.post("/api/v1/auth/refresh")
        assert refresh_resp.status_code == 401

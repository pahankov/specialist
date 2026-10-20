"""Tests for refresh token flow."""
from datetime import datetime, timedelta, timezone as dt_timezone

from tests.conftest import issue_master_refresh, master_access_token


async def _register_with_refresh(client, session, data):
    """Register a master and create a valid refresh token for it."""
    from sqlalchemy import select
    from app.models.user import User

    reg = await client.post("/api/v1/auth/register", json=data)
    assert reg.status_code == 201, reg.text
    user = (await session.execute(
        select(User).where(User.email == data["email"])
    )).scalar_one()
    return user, await issue_master_refresh(session, user)


class TestRefreshToken:
    """Tests for POST /api/v1/auth/refresh and POST /api/v1/auth/logout"""

    async def test_refresh_token_success(self, client, session, test_master_data):
        """Refresh endpoint returns new access token and new refresh token."""
        _, old_refresh = await _register_with_refresh(
            client, session, test_master_data)

        # Refresh
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
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

    async def test_refresh_token_invalid_type(self, client, session):
        """Refresh fails with access token as refresh token."""
        user, _ = await _register_with_refresh(client, session, {
            "name": "Test",
            "email": "invalid_type@example.com",
            "password": "SecurePass123!",
            "phone": "+79990000099",
            "role": "MASTER",
        })
        # Present an access token as the refresh cookie.
        resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": master_access_token(user)},
        )
        assert resp.status_code == 401

    async def test_refresh_token_reuse_within_grace_rotates(
        self, client, session, test_master_data,
    ):
        """Immediate reuse of a just-revoked token rotates again (race grace),
        it does NOT 401 — see test_refresh_rotation_race_absorbed."""
        _, old_refresh = await _register_with_refresh(
            client, session, test_master_data)

        # First refresh — should succeed
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh_resp.status_code == 200
        first_new = refresh_resp.cookies.get("refresh_token")
        assert first_new is not None and first_new != old_refresh

        # Immediate reuse — absorbed by the grace window, rotates once more.
        resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert resp.status_code == 200, resp.text
        assert resp.cookies.get("refresh_token") not in (old_refresh, first_new)

    async def test_refresh_rotation_race_absorbed(
        self, client, session, test_master_data,
    ):
        """Two tabs refreshing at once: the loser reuses the just-revoked
        token within the grace window and still gets a fresh pair (no logout)."""
        _, old_refresh = await _register_with_refresh(
            client, session, test_master_data)

        first = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert first.status_code == 200

        # Loser tab presents the just-revoked token — absorbed, fresh pair.
        second = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert second.status_code == 200, second.text
        assert "access_token" in second.json()

    async def test_refresh_grace_expired_rejected(self, client, session, test_master_data):
        """A revoked token past the grace window stays dead (theft safety)."""
        from sqlalchemy import update
        from app.models.refresh_token import RefreshToken

        _, old_refresh = await _register_with_refresh(
            client, session, test_master_data)

        assert (await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )).status_code == 200

        # Age the revocation beyond the grace window.
        await session.execute(
            update(RefreshToken)
            .where(RefreshToken.token == old_refresh)
            .values(revoked_at=datetime.now(dt_timezone.utc) - timedelta(hours=1))
        )
        await session.commit()

        resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert resp.status_code == 401


class TestLogout:
    """Tests for POST /api/v1/auth/logout"""

    async def test_logout_revokes_refresh_token(
        self, client, session, test_master_data,
    ):
        """Logout revokes the refresh token so it cannot be used for refresh."""
        _, old_refresh = await _register_with_refresh(
            client, session, test_master_data)

        # Logout
        resp = await client.post(
            "/api/v1/auth/logout",
            cookies={"refresh_token": old_refresh},
        )
        assert resp.status_code == 200

        # The stored token is revoked server-side.
        from sqlalchemy import select
        from app.models.refresh_token import RefreshToken

        stored = (await session.execute(
            select(RefreshToken).where(RefreshToken.token == old_refresh)
        )).scalar_one()
        assert stored.is_revoked is True

        # Try refresh with old token — should fail
        refresh_resp = await client.post(
            "/api/v1/auth/refresh",
            cookies={"refresh_token": old_refresh},
        )
        assert refresh_resp.status_code == 401

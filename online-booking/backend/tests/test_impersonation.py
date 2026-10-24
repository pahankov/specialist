"""Superadmin impersonation of any participant (master or client)."""
from datetime import datetime, timezone as dt_timezone

import jwt

from app.config import settings


async def _make_user(session, *, role: str, email: str, active: bool = True):
    from app.models.user import User

    user = User(
        name=f"Target {email}",
        email=email,
        phone=None,
        hashed_password=None,
        role=role,
        is_active=active,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


async def _make_client(session, email="impclient@example.com", active=True):
    from app.models.client_profile import ClientProfile

    user = await _make_user(session, role="CLIENT", email=email, active=active)
    session.add(ClientProfile(user_id=user.id))
    await session.commit()
    return user


async def _make_master(session, email="impmaster@example.com", active=True):
    from app.models.master_profile import MasterProfile

    user = await _make_user(session, role="MASTER", email=email, active=active)
    profile = MasterProfile(user_id=user.id)
    session.add(profile)
    await session.commit()
    await session.refresh(profile)
    return user, profile


class TestParticipantImpersonation:
    async def test_impersonate_client(self, client, session, super_admin_headers):
        target = await _make_client(session)

        resp = await client.post(
            f"/api/v1/admin/users/{target.id}/impersonate",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["role"] == "CLIENT"
        assert data["redirect"] == "/cabinet"
        assert data["user_id"] == target.id

        payload = jwt.decode(
            data["access_token"], settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        assert payload["sub"] == str(target.id)
        assert payload["role"] == "CLIENT"
        assert payload["is_admin"] is False
        assert payload["impersonated_by"] is not None

        # Support sessions must be short-lived, not the regular 24h window.
        now = datetime.now(dt_timezone.utc).timestamp()
        assert payload["exp"] > now
        assert payload["exp"] <= (
            now + settings.IMPERSONATION_TOKEN_EXPIRE_MINUTES * 60 + 5
        )
        assert payload["exp"] < now + 60 * 60

        me = await client.get(
            "/api/v1/client/me",
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert me.status_code == 200, me.text
        assert me.json()["id"] == target.id

    async def test_impersonate_master_by_user_id(self, client, session, super_admin_headers):
        target, profile = await _make_master(session)

        resp = await client.post(
            f"/api/v1/admin/users/{target.id}/impersonate",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["role"] == "MASTER"
        assert data["redirect"] == "/admin/dashboard"
        assert data["user_id"] == target.id

    async def test_admin_target_forbidden(self, client, super_admin_headers,
                                          super_admin_user):
        resp = await client.post(
            f"/api/v1/admin/users/{super_admin_user.id}/impersonate",
            headers=super_admin_headers,
        )
        assert resp.status_code == 403

    async def test_inactive_target_forbidden(self, client, session, super_admin_headers):
        target = await _make_client(session, email="inactive@example.com", active=False)

        resp = await client.post(
            f"/api/v1/admin/users/{target.id}/impersonate",
            headers=super_admin_headers,
        )
        assert resp.status_code == 403

    async def test_unknown_user_404(self, client, super_admin_headers):
        resp = await client.post(
            "/api/v1/admin/users/999999/impersonate",
            headers=super_admin_headers,
        )
        assert resp.status_code == 404

    async def test_regular_master_forbidden(self, client, session, auth_context):
        target = await _make_client(session, email="notforregular@example.com")

        resp = await client.post(
            f"/api/v1/admin/users/{target.id}/impersonate",
            headers=auth_context["headers"],
        )
        assert resp.status_code == 403

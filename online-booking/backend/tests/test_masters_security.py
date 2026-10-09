"""Tests for superadmin security actions: impersonate / password / sessions."""
import jwt

from app.config import settings


class TestImpersonate:
    async def test_impersonate_master(self, client, super_admin_headers, created_master_id):
        """Superadmin gets a working token for the master (audited)."""
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/impersonate",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        payload = jwt.decode(
            resp.json()["access_token"], settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        assert payload["role"] == "MASTER"
        assert payload["is_admin"] is False
        assert "impersonated_by" in payload

    async def test_impersonate_token_actually_works(self, client, super_admin_headers,
                                                    created_master_id):
        """Impersonated token passes master-scoped auth."""
        resp = await client.post(
            f"/api/v1/admin/masters/{created_master_id}/impersonate",
            headers=super_admin_headers,
        )
        token = resp.json()["access_token"]
        me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code in (200, 404)  # 404 only if /me route absent, never 401/403
        assert me.status_code != 401

    async def test_impersonate_missing_master(self, client, super_admin_headers):
        resp = await client.post("/api/v1/admin/masters/999999/impersonate",
                                 headers=super_admin_headers)
        assert resp.status_code == 404

    async def test_impersonate_forbidden_for_master(self, client, auth_context):
        """Regular master cannot impersonate."""
        resp = await client.post(
            f"/api/v1/admin/masters/{auth_context['master_id']}/impersonate",
            headers=auth_context["headers"],
        )
        assert resp.status_code == 403

    async def test_impersonate_admin_target_forbidden(self, client, super_admin_headers,
                                                      session):
        """Cannot impersonate a fellow ADMIN (needs a MasterProfile id)."""
        from app.models.master_profile import MasterProfile
        from app.models.user import User
        admin2 = User(name="A2", email="a2@example.com", hashed_password="x",
                      role="ADMIN", is_active=True, is_verified=True)
        session.add(admin2)
        await session.flush()
        mp = MasterProfile(user_id=admin2.id)
        session.add(mp)
        await session.commit()
        await session.refresh(mp)

        resp = await client.post(f"/api/v1/admin/masters/{mp.id}/impersonate",
                                 headers=super_admin_headers)
        assert resp.status_code == 403


class TestPasswordReset:
    async def test_weak_password_rejected(self, client, super_admin_headers,
                                          created_master_id):
        resp = await client.patch(
            f"/api/v1/admin/masters/{created_master_id}/password",
            json={"password": "123"},
            headers=super_admin_headers,
        )
        assert resp.status_code == 400

    async def test_reset_then_login_with_new_password(self, client, super_admin_headers,
                                                      created_master_id, test_master_data):
        new_pass = "BrandNew456!"
        resp = await client.patch(
            f"/api/v1/admin/masters/{created_master_id}/password",
            json={"password": new_pass},
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text

        login = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"], "password": new_pass,
        })
        assert login.status_code == 200

    async def test_reset_forbidden_for_master(self, client, auth_context):
        resp = await client.patch(
            f"/api/v1/admin/masters/{auth_context['master_id']}/password",
            json={"password": "BrandNew456!"},
            headers=auth_context["headers"],
        )
        assert resp.status_code == 403


class TestSessions:
    async def _login_master(self, client, test_master_data):
        resp = await client.post("/api/v1/auth/login", json={
            "email": test_master_data["email"], "password": test_master_data["password"],
        })
        assert resp.status_code == 200
        return resp
    async def test_list_hides_token_values(self, client, super_admin_headers,
                                            created_master_id, test_master_data):
        await self._login_master(client, test_master_data)
        resp = await client.get(
            f"/api/v1/admin/masters/{created_master_id}/sessions",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        items = resp.json()
        assert len(items) >= 1
        assert all(set(i) == {"id", "created_at", "expires_at"} for i in items)

    async def test_revoke_kills_refresh(self, client, super_admin_headers,
                                        created_master_id, test_master_data):
        await self._login_master(client, test_master_data)

        resp = await client.delete(
            f"/api/v1/admin/masters/{created_master_id}/sessions",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["revoked"] >= 1

        # Same client jar still holds the old refresh cookie -> must be dead
        again = await client.post("/api/v1/auth/refresh")
        assert again.status_code == 401

    async def test_sessions_forbidden_for_master(self, client, auth_context):
        resp = await client.get(
            f"/api/v1/admin/masters/{auth_context['master_id']}/sessions",
            headers=auth_context["headers"],
        )
        assert resp.status_code == 403

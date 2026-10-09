"""Regression: master PATCH / toggle-active / DELETE must not 500.

Covers two real prod bugs:
- status routes were mounted at /admin/{id}/... instead of
  /admin/masters/{id}/... (toggle/suspend/... all 404'd);
- block toggled only `status` while the UI reads `is_active`.
"""
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.utils.security import hash_password


async def _seed_master(session, email="repro_master@example.com"):
    u = User(name="Repro", email=email,
             hashed_password=hash_password("SecurePass123!"),
             role=UserRole.MASTER)
    session.add(u)
    await session.flush()
    mp = MasterProfile(user_id=u.id)
    session.add(mp)
    await session.flush()
    await session.commit()
    return mp.id


class TestMasterMutations:
    async def test_patch_master(self, client, session, super_admin_headers):
        mp_id = await _seed_master(session)
        r = await client.patch(
            f"/api/v1/admin/masters/{mp_id}",
            json={"name": "Repro Renamed"},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Repro Renamed"

    async def test_toggle_master(self, client, session, super_admin_headers):
        mp_id = await _seed_master(session, "repro_toggle@example.com")
        r = await client.post(
            f"/api/v1/admin/masters/{mp_id}/toggle-active",
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Block flips BOTH flags: UI badge/icon read is_active
        assert body["is_active"] is False
        assert body["status"] == "inactive"
        r2 = await client.post(
            f"/api/v1/admin/masters/{mp_id}/toggle-active",
            headers=super_admin_headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["is_active"] is True
        assert r2.json()["status"] == "active"

    async def test_delete_master(self, client, session, super_admin_headers):
        mp_id = await _seed_master(session, "repro_del@example.com")
        r = await client.delete(
            f"/api/v1/admin/masters/{mp_id}",
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text

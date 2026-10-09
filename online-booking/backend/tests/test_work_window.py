"""Work window endpoints: daily hour range driving schedule granules."""


class TestWorkWindow:
    async def _seed_master(self, session):
        from app.models.master_profile import MasterProfile
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        muser = User(name="W", email="windowmaster@example.com",
                     hashed_password=hash_password("SecurePass123!"),
                     role=UserRole.MASTER)
        session.add(muser)
        await session.flush()
        mp = MasterProfile(user_id=muser.id)
        session.add(mp)
        await session.flush()
        await session.commit()
        return muser.id, mp.id

    async def test_defaults_then_update(self, client, session, super_admin_headers):
        _, mp_id = await self._seed_master(session)
        r = await client.get(
            "/api/v1/admin/work-window", params={"master_id": mp_id},
            headers=super_admin_headers,
        )
        assert r.status_code == 200, r.text
        assert (r.json()["start_hour"], r.json()["end_hour"]) == (8, 22)

        u = await client.patch(
            "/api/v1/admin/work-window",
            json={"master_id": mp_id, "start_hour": 3, "end_hour": 23},
            headers=super_admin_headers,
        )
        assert u.status_code == 200, u.text
        assert (u.json()["start_hour"], u.json()["end_hour"]) == (3, 23)

    async def test_invalid_range_rejected(self, client, session, super_admin_headers):
        _, mp_id = await self._seed_master(session)
        r = await client.patch(
            "/api/v1/admin/work-window",
            json={"master_id": mp_id, "start_hour": 23, "end_hour": 3},
            headers=super_admin_headers,
        )
        assert r.status_code == 400

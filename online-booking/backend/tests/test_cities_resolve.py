"""Cities resolve endpoint: DaData picks map to local ids (get-or-create)."""


class TestResolveCity:
    async def _seed_ru(self, session):
        from app.models.country import Country
        session.add(Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7"))
        await session.commit()

    async def test_resolve_creates_then_reuses(self, client, session, super_admin_headers):
        await self._seed_ru(session)
        r1 = await client.post(
            "/api/v1/cities/resolve", json={"name": "Гвардейск"},
            headers=super_admin_headers,
        )
        assert r1.status_code == 200, r1.text
        first_id = r1.json()["id"]
        assert r1.json()["name_ru"] == "Гвардейск"

        r2 = await client.post(
            "/api/v1/cities/resolve", json={"name": "гвардейск"},
            headers=super_admin_headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["id"] == first_id

    async def test_resolve_empty_name_rejected(self, client, session, super_admin_headers):
        await self._seed_ru(session)
        r = await client.post(
            "/api/v1/cities/resolve", json={"name": "   "},
            headers=super_admin_headers,
        )
        assert r.status_code == 400

    async def test_resolve_allowed_for_client(self, client, session):
        """Cabinet/booking city pickers run as CLIENT (was 401 via require_master)."""
        from app.models.user import User, UserRole
        from app.models.client_profile import ClientProfile
        from app.modules.auth.token import create_access_token

        await self._seed_ru(session)
        user = User(name="C", phone="+79990003333", role=UserRole.CLIENT)
        session.add(user)
        await session.flush()
        session.add(ClientProfile(user_id=user.id))
        await session.commit()
        token = create_access_token({
            "sub": str(user.id), "role": "CLIENT", "name": user.name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/cities/resolve", json={"name": "Гвардейск"},
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["name_ru"] == "Гвардейск"

    async def test_resolve_anonymous_rejected(self, client, session):
        await self._seed_ru(session)
        r = await client.post("/api/v1/cities/resolve", json={"name": "Гвардейск"})
        assert r.status_code in (401, 403)

    async def test_resolve_reuses_family_spelling(self, client, session,
                                                 super_admin_headers):
        await self._seed_ru(session)
        r1 = await client.post(
            "/api/v1/cities/resolve", json={"name": "Гвардейск"},
            headers=super_admin_headers,
        )
        assert r1.status_code == 200, r1.text
        r2 = await client.post(
            "/api/v1/cities/resolve", json={"name": "Россия, г Гвардейск"},
            headers=super_admin_headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["id"] == r1.json()["id"]

    async def test_merge_duplicates(self, client, session, super_admin_headers):
        from sqlalchemy import select
        from app.models.country import Country
        from app.models.city import City
        from app.models.user import User

        await self._seed_ru(session)
        co = (await session.execute(
            select(Country).where(Country.code == "RU"))).scalar_one()
        session.add(City(country_id=co.id, name_ru="Дельта", slug="delta"))
        session.add(City(country_id=co.id, name_ru="Россия, г Дельта", slug="delta-ru"))
        await session.flush()
        delta = (await session.execute(
            select(City).where(City.slug == "delta"))).scalar_one()
        delta_id = delta.id
        other = (await session.execute(
            select(City).where(City.slug == "delta-ru"))).scalar_one()
        u = (await session.execute(select(User).limit(1))).scalar_one()
        uid = u.id
        u.city_id = other.id
        await session.commit()

        dry = await client.post("/api/v1/cities/merge-duplicates",
                                headers=super_admin_headers)
        assert dry.status_code == 200, dry.text
        assert dry.json()["apply"] is False
        assert any(delta.id in (g["keeper_id"], *g["merged_ids"])
                   for g in dry.json()["groups"])

        go = await client.post("/api/v1/cities/merge-duplicates?apply=true",
                               headers=super_admin_headers)
        assert go.status_code == 200, go.text
        assert go.json()["remapped_users"] >= 1

        session.expire_all()
        left = (await session.execute(
            select(City).where(City.slug == "delta-ru"))).scalar_one_or_none()
        assert left is None
        uu = (await session.execute(
            select(User).where(User.id == uid))).scalar_one()
        assert uu.city_id == delta_id

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

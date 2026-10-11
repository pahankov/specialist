"""GET /api/v1/admin/profile — own id/name/city for form defaults."""


class TestAdminProfile:
    async def test_master_profile_no_city(self, client, auth_headers):
        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["name"]
        assert body["city_id"] is None

    async def test_master_profile_with_city(self, client, session, auth_headers):
        from sqlalchemy import select
        from app.models.city import City
        from app.models.country import Country
        from app.models.user import User

        country = Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7")
        session.add(country)
        await session.flush()
        city = City(country_id=country.id, name_ru="Казань", name_en="Kazan", slug="kazan")
        session.add(city)
        await session.flush()

        # auth master is the only MASTER user in this fresh DB
        me = (await session.execute(
            select(User).where(User.role == "MASTER")
        )).scalar_one()
        me.city_id = city.id
        await session.commit()

        r = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert r.status_code == 200, r.text
        assert r.json()["city_id"] == city.id
        assert r.json()["city_name"] == "Казань"

    async def test_update_own_city(self, client, session, auth_headers):
        from sqlalchemy import select
        from app.models.city import City
        from app.models.country import Country

        country = Country(code="RU", name_ru="Россия", name_en="Russia", phone_prefix="+7")
        session.add(country)
        await session.flush()
        city = City(country_id=country.id, name_ru="Сочи", name_en="Sochi", slug="sochi")
        session.add(city)
        await session.commit()

        r = await client.patch(
            "/api/v1/admin/profile", json={"city_id": city.id}, headers=auth_headers
        )
        assert r.status_code == 200, r.text
        assert r.json()["city_id"] == city.id
        assert r.json()["city_name"] == "Сочи"

        again = await client.get("/api/v1/admin/profile", headers=auth_headers)
        assert again.json()["city_id"] == city.id

    async def test_update_unknown_city_404(self, client, auth_headers):
        r = await client.patch(
            "/api/v1/admin/profile", json={"city_id": 999999}, headers=auth_headers
        )
        assert r.status_code == 404

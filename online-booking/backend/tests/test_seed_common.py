"""Regression tests for seed_common (deploy scripts canon).

Deploy once failed with IndentationError in this file: backend tests never
import backend/*.py scripts, so nothing caught it. Importing here (module
level) plus behavior checks closes that hole (plus the py_compile CI gate).
"""
import seed_common
from seed_common import (ensure_geography, ensure_master_cities,
                         ensure_reviews, infer_category)


class TestInferCategory:
    def test_nails(self):
        assert infer_category("Маникюр классика") == "Ногти"

    def test_sugaring(self):
        assert infer_category("Шугаринг ног") == "Шугаринг"

    def test_lashes(self):
        assert infer_category("Наращивание ресниц") == "Ресницы и брови"

    def test_fallback(self):
        assert infer_category("Нечто странное") == "Прочее"
        assert infer_category("") == "Прочее"


class TestEnsureGeography:
    async def test_full_seed(self, session):
        from sqlalchemy import select, func
        from app.models.country import Country
        from app.models.city import City

        new_c, new_t = await ensure_geography(session)
        assert (new_c, new_t) == (7, 457)
        assert (await session.execute(
            select(func.count(Country.id)))).scalar() == 7
        assert (await session.execute(
            select(func.count(City.id)))).scalar() == 457

    async def test_idempotent_topup(self, session):
        first = await ensure_geography(session)
        second = await ensure_geography(session)
        assert first == (7, 457)
        assert second == (0, 0)


class TestEnsureReviews:
    async def test_skips_without_appointments(self, session):
        assert await ensure_reviews(session) == 0


class TestEnsureMasterCities:
    async def test_assigns_only_cityless_masters(self, session):
        from sqlalchemy import select
        from app.models.city import City
        from app.models.user import User, UserRole

        await ensure_geography(session)
        kras = (await session.execute(
            select(City).where(City.name_ru == "Краснодар"))).scalar_one()
        m1 = User(name="No City", email="nocity@example.com",
                  phone="+79990001111", role=UserRole.MASTER)
        m2 = User(name="Has City", email="hascity@example.com",
                  phone="+79990002222", role=UserRole.CLIENT,
                  city_id=kras.id)
        session.add_all([m1, m2])
        await session.commit()

        n = await ensure_master_cities(session)
        assert n == 1
        names = (await session.execute(
            select(City.name_ru).join(
                User, User.city_id == City.id).where(User.id == m1.id)
        )).scalar_one()
        assert names in ("Москва", "Санкт-Петербург", "Краснодар")
        # Idempotent: second run touches nothing.
        assert await ensure_master_cities(session) == 0

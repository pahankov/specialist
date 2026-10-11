"""Regression tests for seed_common (deploy scripts canon).

Deploy once failed with IndentationError in this file: backend tests never
import backend/*.py scripts, so nothing caught it. Importing here (module
level) plus behavior checks closes that hole (plus the py_compile CI gate).
"""
import seed_common
from seed_common import ensure_geography, ensure_reviews, infer_category


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

"""P&L report: zero placeholders, totals, filtering and access control."""
from datetime import date
from decimal import Decimal

from app.models.pnl import PnlCategory, PnlExpense, PnlIncome


async def _category(session, name: str, kind: str, active: bool = True):
    category = PnlCategory(
        name=name, kind=kind, is_active=active, description=f"{kind} fixture",
    )
    session.add(category)
    await session.flush()
    await session.refresh(category)
    return category


async def _income(session, category, amount, occurred_on, description=None):
    row = PnlIncome(
        category_id=category.id,
        amount=Decimal(str(amount)),
        occurred_on=occurred_on,
        description=description,
    )
    session.add(row)
    await session.flush()
    return row


async def _expense(session, category, amount, occurred_on, description=None):
    row = PnlExpense(
        category_id=category.id,
        amount=Decimal(str(amount)),
        occurred_on=occurred_on,
        description=description,
    )
    session.add(row)
    await session.flush()
    return row


class TestPnlReport:
    async def test_empty_report_returns_zero_placeholders(
        self, client, session, super_admin_headers,
    ):
        await _category(session, "Услуги", "INCOME")
        await _category(session, "Аренда", "EXPENSE")
        await _category(session, "Старая статья", "EXPENSE", active=False)
        await session.commit()

        resp = await client.get(
            "/api/v1/admin/pnl/report?date_from=2026-01-01&date_to=2026-01-31",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["revenue"] == 0
        assert data["expenses"] == 0
        assert data["profit"] == 0
        assert data["margin"] == 0
        assert data["income_count"] == 0
        assert data["expense_count"] == 0
        assert data["has_data"] is False
        assert data["currency"] == "RUB"
        assert data["date_from"] == "2026-01-01"
        assert data["date_to"] == "2026-01-31"

        # Active categories stay visible as zero lines for a stable layout;
        # inactive empty buckets are hidden.
        assert [line["name"] for line in data["revenue_by_category"]] == ["Услуги"]
        assert data["revenue_by_category"][0]["amount"] == 0
        assert [line["name"] for line in data["expenses_by_category"]] == ["Аренда"]

    async def test_report_computes_revenue_expenses_profit_margin(
        self, client, session, super_admin_headers,
    ):
        services = await _category(session, "Услуги", "INCOME")
        goods = await _category(session, "Товары", "INCOME")
        rent = await _category(session, "Аренда", "EXPENSE")
        materials = await _category(session, "Материалы", "EXPENSE")
        await _income(session, services, "7000.00", date(2026, 2, 10))
        await _income(session, services, "2000.00", date(2026, 2, 11))
        await _income(session, goods, "1000.00", date(2026, 2, 12))
        await _expense(session, rent, "2500.00", date(2026, 2, 1))
        await _expense(session, materials, "1500.00", date(2026, 2, 12))
        await session.commit()

        resp = await client.get(
            "/api/v1/admin/pnl/report?date_from=2026-02-01&date_to=2026-02-28",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()

        assert data["revenue"] == 10000
        assert data["expenses"] == 4000
        assert data["profit"] == 6000
        assert data["margin"] == 60.0
        assert data["income_count"] == 3
        assert data["expense_count"] == 2
        assert data["has_data"] is True

        revenue = {line["name"]: line for line in data["revenue_by_category"]}
        assert revenue["Услуги"]["amount"] == 9000
        assert revenue["Услуги"]["share"] == 90.0
        assert revenue["Товары"]["amount"] == 1000
        assert revenue["Товары"]["share"] == 10.0

        expenses = {line["name"]: line for line in data["expenses_by_category"]}
        assert expenses["Аренда"]["amount"] == 2500
        assert expenses["Аренда"]["share"] == 62.5
        assert expenses["Материалы"]["amount"] == 1500
        assert expenses["Материалы"]["share"] == 37.5

    async def test_report_filters_by_period(
        self, client, session, super_admin_headers,
    ):
        services = await _category(session, "Услуги", "INCOME")
        rent = await _category(session, "Аренда", "EXPENSE")
        await _income(session, services, "500.00", date(2026, 2, 28))
        await _income(session, services, "1000.00", date(2026, 3, 1))
        await _income(session, services, "9999.00", date(2026, 4, 1))
        await _expense(session, rent, "300.00", date(2026, 3, 15))
        await session.commit()

        resp = await client.get(
            "/api/v1/admin/pnl/report?date_from=2026-03-01&date_to=2026-03-31",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["revenue"] == 1000
        assert data["expenses"] == 300
        assert data["profit"] == 700
        assert data["margin"] == 70.0

    async def test_loss_has_negative_profit_and_margin(
        self, client, session, super_admin_headers,
    ):
        services = await _category(session, "Услуги", "INCOME")
        rent = await _category(session, "Аренда", "EXPENSE")
        await _income(session, services, "1000.00", date(2026, 5, 5))
        await _expense(session, rent, "4000.00", date(2026, 5, 5))
        await session.commit()

        resp = await client.get(
            "/api/v1/admin/pnl/report?date_from=2026-05-01&date_to=2026-05-31",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["profit"] == -3000
        assert data["margin"] == -300.0

    async def test_default_period_is_current_month(
        self, client, super_admin_headers,
    ):
        resp = await client.get(
            "/api/v1/admin/pnl/report", headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        today = date.today()
        assert data["date_to"] == today.isoformat()
        assert data["date_from"] == today.replace(day=1).isoformat()

    async def test_invalid_period_rejected(
        self, client, super_admin_headers,
    ):
        resp = await client.get(
            "/api/v1/admin/pnl/report?date_from=2026-06-10&date_to=2026-06-01",
            headers=super_admin_headers,
        )
        assert resp.status_code == 400

    async def test_regular_master_forbidden(self, client, auth_context):
        resp = await client.get(
            "/api/v1/admin/pnl/report", headers=auth_context["headers"],
        )
        assert resp.status_code == 403

    async def test_anonymous_forbidden(self, client):
        resp = await client.get("/api/v1/admin/pnl/report")
        assert resp.status_code in (401, 403)


class TestPnlCategories:
    async def test_lists_categories_and_filters_by_kind(
        self, client, session, super_admin_headers,
    ):
        await _category(session, "Услуги", "INCOME")
        await _category(session, "Аренда", "EXPENSE")
        await session.commit()

        resp = await client.get(
            "/api/v1/admin/pnl/categories", headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        assert {row["kind"] for row in resp.json()} == {"INCOME", "EXPENSE"}

        resp = await client.get(
            "/api/v1/admin/pnl/categories?kind=INCOME",
            headers=super_admin_headers,
        )
        assert resp.status_code == 200, resp.text
        rows = resp.json()
        assert [row["name"] for row in rows] == ["Услуги"]

    async def test_invalid_kind_rejected(
        self, client, super_admin_headers,
    ):
        resp = await client.get(
            "/api/v1/admin/pnl/categories?kind=BOTH",
            headers=super_admin_headers,
        )
        assert resp.status_code == 422

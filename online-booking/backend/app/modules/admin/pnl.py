"""Superadmin P&L report: revenue, expenses, profit and margin by period.

Only the report API is exposed for now. Data is entered through the
accounting pipeline (or a future UI); until then the report returns zeros
while still listing the seeded categories, so the page has a stable shape.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_super_admin
from app.models.pnl import PnlCategory, PnlExpense, PnlIncome
from app.models.user import User
from app.schemas.pnl import PnlCategoryTotal, PnlReportResponse

router = APIRouter(prefix="/pnl", tags=["pnl"])

INCOME = "INCOME"
EXPENSE = "EXPENSE"


def _decimal(value) -> Decimal:
    """Normalize SQLite SUM (float) and PostgreSQL SUM (Decimal) values."""
    return Decimal(str(value or 0))


async def _category_totals(
    db: AsyncSession,
    model,
    kind: str,
    date_from: date,
    date_to: date,
) -> tuple[list[PnlCategoryTotal], Decimal, int]:
    """Aggregate one side of the P&L and keep zero categories visible."""
    categories = (await db.execute(
        select(PnlCategory).where(PnlCategory.kind == kind)
        .order_by(PnlCategory.name.asc())
    )).scalars().all()

    rows = (await db.execute(
        select(
            model.category_id,
            func.coalesce(func.sum(model.amount), 0),
            func.count(model.id),
        )
        .where(
            model.occurred_on >= date_from,
            model.occurred_on <= date_to,
        )
        .group_by(model.category_id)
    )).all()
    by_category = {
        row[0]: (_decimal(row[1]), int(row[2] or 0)) for row in rows
    }

    total = sum((amount for amount, _ in by_category.values()), Decimal("0"))
    count = sum(count for _, count in by_category.values())

    lines: list[PnlCategoryTotal] = []
    for category in categories:
        amount, _ = by_category.get(category.id, (Decimal("0"), 0))
        # Empty inactive buckets are noise; keep active ones so the page
        # always has a stable set of future-number placeholders.
        if amount == 0 and not category.is_active:
            continue
        lines.append(PnlCategoryTotal(
            category_id=category.id,
            name=category.name,
            amount=float(amount),
            share=float(amount / total * 100) if total > 0 else 0.0,
        ))
    lines.sort(key=lambda line: (-line.amount, line.name.lower()))
    return lines, total, count


@router.get("/report", response_model=PnlReportResponse)
async def get_pnl_report(
    date_from: Optional[date] = Query(
        None, description="Period start (inclusive), default: first day of month"
    ),
    date_to: Optional[date] = Query(
        None, description="Period end (inclusive), default: today"
    ),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """P&L for a closed date range. Only superadmins can read company finances."""
    today = date.today()
    period_to = date_to or today
    period_from = date_from or period_to.replace(day=1)
    if period_from > period_to:
        raise HTTPException(status_code=400, detail="Дата начала позже даты окончания")

    revenue_lines, revenue, income_count = await _category_totals(
        db, PnlIncome, INCOME, period_from, period_to,
    )
    expense_lines, expenses, expense_count = await _category_totals(
        db, PnlExpense, EXPENSE, period_from, period_to,
    )

    profit = revenue - expenses
    margin = (profit / revenue * 100) if revenue > 0 else Decimal("0")
    return PnlReportResponse(
        date_from=period_from,
        date_to=period_to,
        revenue=float(revenue),
        expenses=float(expenses),
        profit=float(profit),
        margin=round(float(margin), 2),
        income_count=income_count,
        expense_count=expense_count,
        has_data=bool(income_count or expense_count),
        revenue_by_category=revenue_lines,
        expenses_by_category=expense_lines,
    )


@router.get("/categories")
async def list_pnl_categories(
    kind: Optional[str] = Query(None, pattern="^(INCOME|EXPENSE)$"),
    admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    """Category reference for future entry forms and admin checks."""
    query = select(PnlCategory).order_by(
        PnlCategory.kind.asc(), PnlCategory.name.asc(),
    )
    if kind:
        query = query.where(PnlCategory.kind == kind)
    rows = (await db.execute(query)).scalars().all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "kind": row.kind,
            "description": row.description,
            "is_active": bool(row.is_active),
        }
        for row in rows
    ]

"""P&L report schemas."""
from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class PnlCategoryTotal(BaseModel):
    """One category line in the report (zero when nothing was posted)."""

    category_id: int
    name: str
    amount: float = 0.0
    share: float = 0.0


class PnlReportResponse(BaseModel):
    """Period report: revenue/expenses/profit/margin plus category detail."""

    date_from: date
    date_to: date
    currency: str = "RUB"
    revenue: float = 0.0
    expenses: float = 0.0
    profit: float = 0.0
    margin: float = 0.0
    income_count: int = 0
    expense_count: int = 0
    has_data: bool = False
    revenue_by_category: list[PnlCategoryTotal] = Field(default_factory=list)
    expenses_by_category: list[PnlCategoryTotal] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

"""Profit & Loss (P&L) domain: categories, income and expense entries.

Money is stored as Numeric(14, 2); dates are calendar dates (no timezone)
because a P&L period is defined in whole days. Entries are intentionally
separate tables: income and expense are different business events, and the
report aggregates each side independently before computing profit/margin.

The feature ships ready for data but starts empty: categories are seeded by
the migration, while income/expense tables stay at zero until accounting
starts posting real numbers.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PnlCategory(Base):
    """A reporting bucket for one side of the P&L."""

    __tablename__ = "pnl_categories"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    # INCOME | EXPENSE (kept as a string so SQLite/PostgreSQL share the model)
    kind = Column(String(16), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    incomes = relationship("PnlIncome", back_populates="category")
    expenses = relationship("PnlExpense", back_populates="category")

    __table_args__ = (
        UniqueConstraint("name", "kind", name="uq_pnl_category_name_kind"),
        Index("ix_pnl_categories_kind_active", "kind", "is_active"),
    )


class _PnlEntryMixin:
    """Shared columns for income and expense entries."""

    id = Column(Integer, primary_key=True)
    category_id = Column(
        Integer,
        ForeignKey("pnl_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount = Column(Numeric(14, 2), nullable=False)
    occurred_on = Column(Date, nullable=False, index=True)
    description = Column(Text, nullable=True)
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class PnlIncome(_PnlEntryMixin, Base):
    """Money earned by the business in a P&L period."""

    __tablename__ = "pnl_incomes"

    category = relationship("PnlCategory", back_populates="incomes")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_pnl_incomes_amount_positive"),
    )


class PnlExpense(_PnlEntryMixin, Base):
    """Money spent by the business in a P&L period."""

    __tablename__ = "pnl_expenses"

    category = relationship("PnlCategory", back_populates="expenses")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_pnl_expenses_amount_positive"),
    )

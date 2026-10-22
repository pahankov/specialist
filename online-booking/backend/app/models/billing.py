"""Master billing, bonus and referral domain.

All money is stored as Numeric(10, 2). A master has one billing account
(created lazily from the trial dates on MasterProfile). Charges live in
`billing_invoices`; earned money lives in `billing_credits` and is applied
FIFO to the oldest open invoice. Everything is manual-payment friendly:
a superadmin records a payment, the ledger decides access immediately.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, Numeric,
    String, Text, UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base


def _now():
    return datetime.now(timezone.utc)


class MasterBillingAccount(Base):
    __tablename__ = "master_billing_accounts"

    id = Column(Integer, primary_key=True)
    master_id = Column(
        Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    trial_started_at = Column(DateTime(timezone=True), nullable=False)
    trial_ends_at = Column(DateTime(timezone=True), nullable=False)
    # Day 0 of the recurring ladder; invoices are issued from here.
    billing_started_at = Column(DateTime(timezone=True), nullable=False)
    referral_code = Column(String(16), nullable=False, unique=True, index=True)
    # trial | active | readonly | paused | suspended
    access_status = Column(String(20), nullable=False, default="trial", index=True)
    review_flag = Column(Boolean, nullable=False, default=False)
    # Set when >30% of prompted visits are unconfirmed. Cleared manually.
    bonus_blocked_until = Column(DateTime(timezone=True), nullable=True)
    # End of the period covered by a confirmed prepayment. Display only:
    # the actual money lives in a long-lived prepayment credit and is
    # consumed by future monthly invoices through the regular ledger.
    prepaid_until = Column(DateTime(timezone=True), nullable=True)
    last_processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    master = relationship(
        "MasterProfile", back_populates="billing_account",
        foreign_keys=[master_id],
    )

    __table_args__ = (
        Index("ix_billing_accounts_status", "access_status"),
    )


class BillingInvoice(Base):
    __tablename__ = "billing_invoices"

    id = Column(Integer, primary_key=True)
    master_id = Column(
        Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # 1 = month 1 (250), 2 = month 2 (250), 3+ = 500. Negative indexes are
    # prepayment invoices: they never enter the monthly ladder, are excluded
    # from access checks, and turn into a prepayment credit when paid.
    period_index = Column(Integer, nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    # Sum of the monthly invoices covered by a prepayment, before the annual
    # discount. Kept on the invoice so the exact credit can be recreated.
    base_amount = Column(Numeric(10, 2), nullable=True)
    credits_applied = Column(Numeric(10, 2), nullable=False, default=0)
    paid_amount = Column(Numeric(10, 2), nullable=False, default=0)
    # monthly | prepay_month | prepay_year
    kind = Column(String(24), nullable=False, default="monthly",
                  server_default="monthly", index=True)
    months = Column(Integer, nullable=False, default=1, server_default="1")
    # open | paid | void
    status = Column(String(20), nullable=False, default="open", index=True)
    issue_at = Column(DateTime(timezone=True), nullable=False)
    due_at = Column(DateTime(timezone=True), nullable=False)
    block_at = Column(DateTime(timezone=True), nullable=False)
    period_start = Column(DateTime(timezone=True), nullable=True)
    period_end = Column(DateTime(timezone=True), nullable=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    payment_method = Column(String(40), nullable=True)
    note = Column(Text, nullable=True)
    notified_at = Column(DateTime(timezone=True), nullable=True)
    overdue_notified_at = Column(DateTime(timezone=True), nullable=True)
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    master = relationship("MasterProfile", foreign_keys=[master_id])
    payments = relationship("BillingPayment", back_populates="invoice",
                            cascade="all, delete-orphan")
    credit_applications = relationship("BillingCreditApplication",
                                       back_populates="invoice",
                                       cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("master_id", "period_index",
                         name="uq_billing_invoice_period"),
        Index("ix_billing_invoices_master_status", "master_id", "status"),
    )


class BillingCredit(Base):
    __tablename__ = "billing_credits"

    id = Column(Integer, primary_key=True)
    master_id = Column(
        Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    # client_bonus | referral_bonus | manual
    source = Column(String(30), nullable=False, index=True)
    source_ref = Column(String(80), nullable=True)
    amount = Column(Numeric(10, 2), nullable=False)
    remaining = Column(Numeric(10, 2), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    expired_at = Column(DateTime(timezone=True), nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    applications = relationship("BillingCreditApplication",
                                back_populates="credit",
                                cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_billing_credits_master_remaining", "master_id", "remaining"),
    )


class BillingCreditApplication(Base):
    __tablename__ = "billing_credit_applications"

    id = Column(Integer, primary_key=True)
    credit_id = Column(
        Integer, ForeignKey("billing_credits.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    invoice_id = Column(
        Integer, ForeignKey("billing_invoices.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    amount = Column(Numeric(10, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now)

    credit = relationship("BillingCredit", back_populates="applications")
    invoice = relationship("BillingInvoice", back_populates="credit_applications")

    __table_args__ = (
        UniqueConstraint("credit_id", "invoice_id",
                         name="uq_billing_credit_invoice"),
    )


class BillingPayment(Base):
    __tablename__ = "billing_payments"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(
        Integer, ForeignKey("billing_invoices.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    amount = Column(Numeric(10, 2), nullable=False)
    method = Column(String(40), nullable=False, default="manual")
    note = Column(Text, nullable=True)
    created_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    created_at = Column(DateTime(timezone=True), default=_now)

    invoice = relationship("BillingInvoice", back_populates="payments")


class ClientBonusAward(Base):
    __tablename__ = "client_bonus_awards"

    id = Column(Integer, primary_key=True)
    master_id = Column(
        Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    trial_started_at = Column(DateTime(timezone=True), nullable=False)
    trial_ends_at = Column(DateTime(timezone=True), nullable=False)
    eligible_count = Column(Integer, nullable=False, default=0)
    max_count = Column(Integer, nullable=False, default=10)
    amount = Column(Numeric(10, 2), nullable=False, default=0)
    # pending | credited | rejected | blocked
    status = Column(String(20), nullable=False, default="pending")
    total_candidates = Column(Integer, nullable=False, default=0)
    unconfirmed_count = Column(Integer, nullable=False, default=0)
    review_flagged = Column(Boolean, nullable=False, default=False)
    details = Column(JSON, nullable=True)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)


class ReferralClick(Base):
    __tablename__ = "referral_clicks"

    id = Column(Integer, primary_key=True)
    master_id = Column(
        Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    token = Column(String(80), nullable=False, unique=True, index=True)
    clicked_at = Column(DateTime(timezone=True), default=_now)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_by_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    used_at = Column(DateTime(timezone=True), nullable=True)


class MasterReferral(Base):
    __tablename__ = "master_referrals"

    id = Column(Integer, primary_key=True)
    referrer_master_id = Column(
        Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    referred_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True,
    )
    referred_master_id = Column(
        Integer, ForeignKey("master_profiles.id", ondelete="CASCADE"),
        nullable=True, unique=True, index=True,
    )
    code = Column(String(16), nullable=False)
    clicked_at = Column(DateTime(timezone=True), nullable=False)
    registered_at = Column(DateTime(timezone=True), default=_now)
    evaluated_at = Column(DateTime(timezone=True), nullable=True)
    # pending | qualified | rejected
    status = Column(String(20), nullable=False, default="pending", index=True)
    qualified_count = Column(Integer, nullable=False, default=0)
    amount = Column(Numeric(10, 2), nullable=False, default=0)
    reject_reason = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now)

    referrer = relationship("MasterProfile", foreign_keys=[referrer_master_id])
    referred_master = relationship("MasterProfile", foreign_keys=[referred_master_id])
    referred_user = relationship("User", foreign_keys=[referred_user_id])

    __table_args__ = (
        Index("ix_master_referrals_referrer_status",
              "referrer_master_id", "status"),
    )

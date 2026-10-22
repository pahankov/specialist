"""Billing ladder, client bonus, referrals, blocking and visit prompts."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.appointment import Appointment
from app.models.billing import (
    BillingCredit,
    BillingInvoice,
    ClientBonusAward,
    MasterBillingAccount,
    MasterReferral,
    ReferralClick,
)
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.utils.security import hash_password


NOW = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


async def _mk_user(session, name, email, role=UserRole.CLIENT, social=None):
    kwargs = {}
    if social == "vk":
        kwargs["vk_user_id"] = abs(hash(email)) % 10_000_000 + 1
    elif social == "yandex":
        kwargs["yandex_user_id"] = str(abs(hash(email)) % 10_000_000 + 1)
    elif social == "max":
        kwargs["max_user_id"] = abs(hash(email)) % 10_000_000 + 1
    user = User(
        name=name, email=email, hashed_password=hash_password("SecurePass123!"),
        role=role, is_active=True,
        **kwargs,
    )
    session.add(user)
    await session.flush()
    return user


async def _mk_master(session, name, email, social="vk", start=NOW):
    user = await _mk_user(session, name, email, UserRole.MASTER, social)
    mp = MasterProfile(
        user_id=user.id,
        trial_ends_at=start + timedelta(days=14),
        status="active", is_active=True,
    )
    session.add(mp)
    await session.flush()
    from app.services.billing import ensure_account
    account = await ensure_account(session, mp, now=start)
    account.trial_started_at = start
    account.trial_ends_at = start + timedelta(days=14)
    account.billing_started_at = start
    await session.commit()
    return user, mp, account


async def _mk_client(session, name, email, social="vk"):
    user = await _mk_user(session, name, email, UserRole.CLIENT, social)
    profile = ClientProfile(user_id=user.id)
    session.add(profile)
    await session.flush()
    return user, profile


async def _mk_booking(
    session, master_id, client_id, *, created_at, price=1000,
    role="client", status="completed", day=1, confirmed=True,
    appointment_date=None,
):
    appointment = Appointment(
        master_id=master_id, client_id=client_id,
        appointment_date=appointment_date or created_at,
        status=status, price=price, duration_minutes=60,
        created_by_role=role, created_by_user_id=client_id,
        created_at=created_at,
        visit_prompt_sent_at=created_at if role == "client" else None,
        visit_confirmation_status=("confirmed" if confirmed else "pending")
        if role == "client" else None,
    )
    session.add(appointment)
    await session.flush()
    return appointment


class TestBillingScope:
    async def test_superuser_profile_is_never_billed(
            self, session, super_admin_user_with_profile):
        from app.services.billing import billing_overview, process_master

        mp = super_admin_user_with_profile["master_profile"]
        result = await process_master(session, mp.id, now=NOW + timedelta(days=30))
        assert result is None
        account = (await session.execute(
            select(MasterBillingAccount).where(
                MasterBillingAccount.master_id == mp.id)
        )).scalar_one_or_none()
        assert account is None
        assert await billing_overview(session, now=NOW + timedelta(days=30)) == []

    async def test_client_draft_is_not_billed(self, session):
        from app.services.billing import billing_overview, process_master

        user = await _mk_user(session, "Draft", "draft@example.com")
        mp = MasterProfile(
            user_id=user.id, status="inactive", is_active=False,
        )
        session.add(mp)
        await session.flush()

        assert await process_master(session, mp.id, now=NOW) is None
        assert await billing_overview(session, now=NOW) == []
        account = (await session.execute(
            select(MasterBillingAccount).where(
                MasterBillingAccount.master_id == mp.id)
        )).scalar_one_or_none()
        assert account is None

    async def test_deactivated_master_is_unbilled_and_suspended(self, session):
        from app.services.billing import process_master

        _user, mp, account = await _mk_master(
            session, "Inactive", "inactive@example.com")
        mp.is_active = False
        mp.status = "inactive"
        await session.flush()

        result = await process_master(
            session, mp.id, now=NOW + timedelta(days=30))
        assert result["access_status"] == "suspended"
        assert account.access_status == "suspended"
        invoices = (await session.execute(
            select(BillingInvoice).where(BillingInvoice.master_id == mp.id)
        )).scalars().all()
        assert invoices == []

    async def test_manual_credit_endpoint_skips_superuser_profile(
            self, client, session, super_admin_user_with_profile,
            super_admin_headers_2):
        mp = super_admin_user_with_profile["master_profile"]
        resp = await client.post(
            f"/api/v1/admin/billing/masters/{mp.id}/credits",
            json={"amount": 25, "note": "must not credit admin"},
            headers=super_admin_headers_2,
        )
        assert resp.status_code == 404
        credits = (await session.execute(
            select(BillingCredit).where(BillingCredit.master_id == mp.id)
        )).scalars().all()
        assert credits == []


class TestTrialAndInvoices:
    async def test_trial_is_14_days_and_invoice_ladder(self, session):
        from app.services.billing import process_master

        _user, mp, account = await _mk_master(session, "M", "m@example.com")
        assert (account.trial_ends_at - account.trial_started_at).days == 14

        result = await process_master(session, mp.id, now=NOW + timedelta(days=15))
        assert result["access_status"] == "active"
        invoice = (await session.execute(
            select(BillingInvoice).where(BillingInvoice.master_id == mp.id)
        )).scalar_one()
        assert float(invoice.amount) == 250
        assert invoice.period_index == 1
        assert invoice.status == "open"

        result = await process_master(session, mp.id, now=NOW + timedelta(days=22))
        assert result["access_status"] == "readonly"
        invoice = (await session.execute(
            select(BillingInvoice).where(BillingInvoice.master_id == mp.id)
        )).scalar_one()
        assert invoice.due_at.date() == (NOW + timedelta(days=21)).date()

    async def test_month_two_and_three_amounts(self, session):
        from app.services.billing import process_master

        _user, mp, _account = await _mk_master(session, "M2", "m2@example.com")
        await process_master(session, mp.id, now=NOW + timedelta(days=80))
        invoices = (await session.execute(
            select(BillingInvoice)
            .where(BillingInvoice.master_id == mp.id)
            .order_by(BillingInvoice.period_index)
        )).scalars().all()
        assert [float(i.amount) for i in invoices] == [250, 250, 500]


class TestClientBonus:
    async def test_ten_eligible_clients_pay_the_first_invoice(self, session):
        from app.services.billing import process_master

        _muser, mp, _account = await _mk_master(session, "Bonus", "bonus@example.com")
        for i in range(10):
            _cu, cp = await _mk_client(
                session, f"C{i}", f"bonus-c{i}@example.com", "vk")
            await _mk_booking(
                session, mp.id, cp.id,
                created_at=NOW + timedelta(days=1, hours=i),
                appointment_date=NOW + timedelta(days=1 + i // 3, hours=i % 3),
            )
        await session.commit()

        await process_master(session, mp.id, now=NOW + timedelta(days=22))
        award = (await session.execute(
            select(ClientBonusAward).where(ClientBonusAward.master_id == mp.id)
        )).scalar_one()
        assert award.eligible_count == 10
        assert float(award.amount) == 250
        assert award.status == "credited"
        credit = (await session.execute(
            select(BillingCredit).where(BillingCredit.master_id == mp.id)
        )).scalar_one()
        assert float(credit.amount) == 250
        invoice = (await session.execute(
            select(BillingInvoice).where(BillingInvoice.master_id == mp.id)
        )).scalar_one()
        assert invoice.status == "paid"
        assert float(invoice.credits_applied) == 250

    async def test_filters_master_price_social_and_caps(self, session):
        from app.services.billing import compute_client_bonus

        _muser, mp, account = await _mk_master(
            session, "Filter", "filter@example.com")
        # Master-created: never counts.
        _cu, cp = await _mk_client(session, "MC", "mc@example.com", "vk")
        await _mk_booking(session, mp.id, cp.id,
                          created_at=NOW + timedelta(days=1), role="master")
        # Under 500: never counts.
        _cu2, cp2 = await _mk_client(session, "Cheap", "cheap@example.com", "vk")
        await _mk_booking(session, mp.id, cp2.id,
                          created_at=NOW + timedelta(days=2), price=499)
        # No social: never counts.
        _cu3, cp3 = await _mk_client(session, "NoSoc", "nosoc@example.com", None)
        await _mk_booking(session, mp.id, cp3.id,
                          created_at=NOW + timedelta(days=3))
        # Same client twice on two days proves the client, but is paid once.
        _cu4, cp4 = await _mk_client(session, "Twice", "twice@example.com", "vk")
        await _mk_booking(session, mp.id, cp4.id,
                          created_at=NOW + timedelta(days=4))
        await _mk_booking(session, mp.id, cp4.id,
                          created_at=NOW + timedelta(days=5))
        # Third booking from the same client is capped by the 2-per-client rule.
        await _mk_booking(session, mp.id, cp4.id,
                          created_at=NOW + timedelta(days=6))
        await session.commit()

        calc = await compute_client_bonus(session, mp.id, account, now=NOW + timedelta(days=22))
        assert calc["total_candidates"] == 2
        assert calc["eligible_count"] == 1
        assert float(calc["amount"]) == 25

    async def test_three_per_day_and_quality_flag(self, session):
        from app.services.billing import compute_client_bonus

        _muser, mp, account = await _mk_master(
            session, "Day", "day@example.com")
        for i in range(5):
            _cu, cp = await _mk_client(
                session, f"D{i}", f"day-c{i}@example.com", "vk")
            await _mk_booking(
                session, mp.id, cp.id,
                created_at=NOW + timedelta(days=1, hours=i),
                confirmed=(i < 3),
            )
        await session.commit()

        calc = await compute_client_bonus(session, mp.id, account, now=NOW + timedelta(days=22))
        assert calc["total_candidates"] == 3
        # The quality filter looks at every prompted visit, including rows
        # that were over the bonus caps: 2 of 5 unconfirmed = 40%.
        assert calc["prompted_count"] == 5
        assert calc["unconfirmed_count"] == 2
        assert calc["review_flag"] is True

        # One more prompted and confirmed row lowers the ratio but keeps it
        # above the 30% threshold (2 of 6 = 33%).
        await _mk_booking(
            session, mp.id, cp.id,
            created_at=NOW + timedelta(days=2),
            confirmed=True,
        )
        await session.commit()
        calc = await compute_client_bonus(session, mp.id, account, now=NOW + timedelta(days=22))
        assert calc["prompted_count"] == 6
        assert calc["unconfirmed_count"] == 2
        assert calc["review_flag"] is True

    async def test_quality_counts_prompts_even_if_booking_was_cancelled(
            self, session):
        from app.services.billing import compute_client_bonus

        _muser, mp, account = await _mk_master(
            session, "Cancelled", "quality-cancelled@example.com")
        _cu, cp = await _mk_client(
            session, "QC", "quality-cancelled-client@example.com", "vk")
        await _mk_booking(
            session, mp.id, cp.id,
            created_at=NOW + timedelta(days=1), status="cancelled",
            confirmed=False,
        )
        await session.commit()

        calc = await compute_client_bonus(
            session, mp.id, account, now=NOW + timedelta(days=22))
        assert calc["eligible_count"] == 0
        assert calc["prompted_count"] == 1
        assert calc["unconfirmed_count"] == 1
        assert calc["review_flag"] is True

    async def test_quality_flag_keeps_month_one_bonus(self, session):
        from app.services.billing import process_master

        _muser, mp, account = await _mk_master(
            session, "Quality", "quality@example.com")
        for i in range(5):
            _cu, cp = await _mk_client(
                session, f"Q{i}", f"quality-c{i}@example.com", "vk")
            await _mk_booking(
                session, mp.id, cp.id,
                created_at=NOW + timedelta(days=1, hours=i),
                appointment_date=NOW + timedelta(days=1 + i),
                confirmed=(i < 3),
            )
        await session.commit()

        await process_master(session, mp.id, now=NOW + timedelta(days=22))
        award = (await session.execute(
            select(ClientBonusAward).where(ClientBonusAward.master_id == mp.id)
        )).scalar_one()
        assert award.status == "credited"
        assert award.review_flagged is True
        assert float(award.amount) == 125
        refreshed = (await session.execute(
            select(MasterBillingAccount).where(
                MasterBillingAccount.master_id == mp.id)
        )).scalar_one()
        assert refreshed.review_flag is True
        assert refreshed.bonus_blocked_until is not None


class TestClientBonusOwnership:
    async def test_client_generates_bonus_for_one_master_only(self, session):
        from app.services.billing import compute_client_bonus

        _au, a_mp, a_account = await _mk_master(
            session, "OwnerA", "owner-a@example.com")
        _bu, b_mp, b_account = await _mk_master(
            session, "OwnerB", "owner-b@example.com")
        _cu, cp = await _mk_client(
            session, "Shared", "shared-client@example.com", "vk")
        await _mk_booking(
            session, a_mp.id, cp.id,
            created_at=NOW + timedelta(days=1),
            appointment_date=NOW + timedelta(days=1),
        )
        await _mk_booking(
            session, b_mp.id, cp.id,
            created_at=NOW + timedelta(days=2),
            appointment_date=NOW + timedelta(days=2),
        )
        await session.commit()

        calc_a = await compute_client_bonus(
            session, a_mp.id, a_account, now=NOW + timedelta(days=22))
        calc_b = await compute_client_bonus(
            session, b_mp.id, b_account, now=NOW + timedelta(days=22))
        assert calc_a["eligible_count"] == 1
        assert calc_b["eligible_count"] == 0


class TestCreditPriority:
    async def test_client_bonus_is_applied_before_referral(self, session):
        from decimal import Decimal
        from app.services.billing import apply_credits

        _user, mp, account = await _mk_master(
            session, "Priority", "priority@example.com")
        # Create the referral credit first so FIFO-by-id would pick it first.
        referral = BillingCredit(
            master_id=mp.id, source="referral_bonus", source_ref="ref:test",
            amount=Decimal("125"), remaining=Decimal("125"),
            expires_at=NOW + timedelta(days=90), created_at=NOW,
        )
        session.add(referral)
        await session.flush()
        client = BillingCredit(
            master_id=mp.id, source="client_bonus", source_ref="bonus:test",
            amount=Decimal("50"), remaining=Decimal("50"),
            expires_at=NOW + timedelta(days=90), created_at=NOW,
        )
        session.add(client)
        await session.flush()
        invoice = BillingInvoice(
            master_id=mp.id, period_index=1, amount=Decimal("75"),
            credits_applied=Decimal("0"), paid_amount=Decimal("0"),
            status="open", issue_at=NOW, due_at=NOW + timedelta(days=6),
            block_at=NOW + timedelta(days=6), period_start=NOW,
            period_end=NOW + timedelta(days=30),
            created_at=NOW, updated_at=NOW,
        )
        session.add(invoice)
        await session.flush()

        await apply_credits(session, mp.id, now=NOW)
        assert float(invoice.credits_applied) == 75
        assert float(client.remaining) == 0
        assert float(referral.remaining) == 100


class TestReferrals:
    async def test_two_masters_with_different_socials_and_seven_bookings(self, session):
        from app.services.billing import (
            attribute_referral, create_referral_click, process_master,
        )

        a_user, a_mp, a_account = await _mk_master(
            session, "A", "ref-a@example.com", "vk")
        b_user = await _mk_user(session, "B", "ref-b@example.com", UserRole.CLIENT, "yandex")
        await session.commit()

        click = await create_referral_click(session, a_account.referral_code, now=NOW)
        attr = await attribute_referral(session, b_user, click["token"], now=NOW)
        assert attr["status"] == "pending"
        await session.commit()

        b_user.role = UserRole.MASTER
        b_mp = MasterProfile(
            user_id=b_user.id, trial_ends_at=NOW + timedelta(days=14),
            status="active", is_active=True,
        )
        session.add(b_mp)
        await session.flush()
        from app.services.billing import ensure_account, link_referral_to_master
        b_account = await ensure_account(session, b_mp, now=NOW)
        b_account.trial_started_at = NOW
        b_account.trial_ends_at = NOW + timedelta(days=14)
        b_account.billing_started_at = NOW
        await link_referral_to_master(session, b_user, b_mp)
        await session.commit()

        # 7 bookings: 3 clients × 2 on different days + 1 extra client.
        for i in range(3):
            _cu, cp = await _mk_client(
                session, f"R{i}", f"ref-client{i}@example.com", "max")
            await _mk_booking(session, b_mp.id, cp.id,
                              created_at=NOW + timedelta(days=1, hours=i))
            await _mk_booking(session, b_mp.id, cp.id,
                              created_at=NOW + timedelta(days=2, hours=i))
        _cu, cp = await _mk_client(
            session, "R3", "ref-client3@example.com", "max")
        await _mk_booking(session, b_mp.id, cp.id,
                          created_at=NOW + timedelta(days=3))
        await session.commit()

        await process_master(session, b_mp.id, now=NOW + timedelta(days=22))
        referral = (await session.execute(
            select(MasterReferral).where(MasterReferral.referred_user_id == b_user.id)
        )).scalar_one()
        assert referral.status == "qualified"
        assert referral.qualified_count == 7
        assert float(referral.amount) == 125
        credit = (await session.execute(
            select(BillingCredit).where(
                BillingCredit.master_id == a_mp.id,
                BillingCredit.source == "referral_bonus",
            )
        )).scalar_one()
        assert float(credit.amount) == 125

    async def test_same_social_provider_is_rejected(self, session):
        from app.services.billing import (
            attribute_referral, create_referral_click, process_master,
        )

        _a_user, _a_mp, a_account = await _mk_master(
            session, "A2", "ref-a2@example.com", "vk")
        b_user = await _mk_user(session, "B2", "ref-b2@example.com", UserRole.CLIENT, "vk")
        await session.commit()
        click = await create_referral_click(session, a_account.referral_code, now=NOW)
        await attribute_referral(session, b_user, click["token"], now=NOW)

        b_user.role = UserRole.MASTER
        b_mp = MasterProfile(
            user_id=b_user.id, trial_ends_at=NOW + timedelta(days=14),
            status="active", is_active=True,
        )
        session.add(b_mp)
        await session.flush()
        from app.services.billing import ensure_account, link_referral_to_master
        b_account = await ensure_account(session, b_mp, now=NOW)
        b_account.trial_started_at = NOW
        b_account.trial_ends_at = NOW + timedelta(days=14)
        b_account.billing_started_at = NOW
        await link_referral_to_master(session, b_user, b_mp)
        await session.commit()

        await process_master(session, b_mp.id, now=NOW + timedelta(days=22))
        referral = (await session.execute(
            select(MasterReferral).where(MasterReferral.referred_user_id == b_user.id)
        )).scalar_one()
        assert referral.status == "rejected"
        assert "совпадают" in (referral.reject_reason or "")


class TestPrepayment:
    async def test_annual_prepay_quote_is_20_percent_off_next_12_months(
            self, session):
        from app.services.billing import create_prepayment

        _user, mp, _account = await _mk_master(
            session, "Prepay", "prepay@example.com")
        invoice, quote = await create_prepayment(session, mp.id, 12, now=NOW)
        assert quote["base_amount"] == 5500
        assert quote["amount"] == 4400
        assert quote["discount_percent"] == 20
        assert invoice.kind == "prepay_year"
        assert invoice.period_index == -1
        assert invoice.months == 12
        assert float(invoice.amount) == 4400
        assert float(invoice.base_amount) == 5500
        assert invoice.period_start.date() == (NOW + timedelta(days=15)).date()
        assert invoice.period_end.date() == (NOW + timedelta(days=375)).date()

    async def test_paid_annual_prepay_creates_credit_that_pays_future_invoices(
            self, session):
        from decimal import Decimal
        from app.services.billing import (
            create_prepayment, process_master, record_payment,
            serialize_billing,
        )

        _user, mp, account = await _mk_master(
            session, "PrepayPay", "prepay-pay@example.com")
        invoice, _quote = await create_prepayment(session, mp.id, 12, now=NOW)
        await record_payment(
            session, invoice, amount=Decimal("4400"), method="manual",
            now=NOW + timedelta(days=1))
        await session.flush()

        account = (await session.execute(
            select(MasterBillingAccount).where(
                MasterBillingAccount.master_id == mp.id)
        )).scalar_one()
        assert account.prepaid_until.date() == (NOW + timedelta(days=375)).date()
        credit = (await session.execute(
            select(BillingCredit).where(
                BillingCredit.master_id == mp.id,
                BillingCredit.source == "prepayment",
            )
        )).scalar_one()
        assert float(credit.amount) == 5500
        assert float(credit.remaining) == 5500

        await process_master(session, mp.id, now=NOW + timedelta(days=16))
        first = (await session.execute(
            select(BillingInvoice).where(
                BillingInvoice.master_id == mp.id,
                BillingInvoice.period_index == 1,
            )
        )).scalar_one()
        assert first.status == "paid"
        assert float(first.credits_applied) == 250
        assert float(credit.remaining) == 5250

        data = await serialize_billing(
            session, mp.id, now=NOW + timedelta(days=16))
        assert data["prepaid_until"] is not None
        assert data["next_payment_amount"] == 0
        assert data["balance"]["due"] == 0
        assert data["balance"]["credit"] == 5250
        assert data["prepay"]["available"] is False

    async def test_monthly_prepay_and_current_invoice_block(self, session):
        from decimal import Decimal
        from app.services.billing import (
            BillingValidationError, create_prepayment, process_master,
            record_payment,
        )

        _user, mp, _account = await _mk_master(
            session, "PrepayMonth", "prepay-month@example.com")
        invoice, quote = await create_prepayment(session, mp.id, 1, now=NOW)
        assert quote["amount"] == 250
        assert quote["discount_percent"] == 0
        assert invoice.kind == "prepay_month"
        await record_payment(
            session, invoice, amount=Decimal("250"), method="manual",
            now=NOW + timedelta(days=1))
        await process_master(session, mp.id, now=NOW + timedelta(days=16))
        monthly = (await session.execute(
            select(BillingInvoice).where(
                BillingInvoice.master_id == mp.id,
                BillingInvoice.period_index == 1,
            )
        )).scalar_one()
        assert monthly.status == "paid"

        _user2, mp2, _account2 = await _mk_master(
            session, "PrepayBlocked", "prepay-blocked@example.com")
        await process_master(session, mp2.id, now=NOW + timedelta(days=22))
        with pytest.raises(BillingValidationError):
            await create_prepayment(
                session, mp2.id, 1, now=NOW + timedelta(days=22))

    async def test_prepay_endpoint_and_duplicate_guard(self, client, session):
        from app.modules.auth.token import create_access_token

        user, mp, account = await _mk_master(
            session, "PrepayAPI", "prepay-api@example.com")
        # The endpoint runs at real "now"; keep this master inside the trial
        # so the quote is available and deterministic.
        current = datetime.now(timezone.utc)
        account.trial_started_at = current
        account.trial_ends_at = current + timedelta(days=14)
        account.billing_started_at = current
        mp.trial_ends_at = account.trial_ends_at
        await session.commit()
        token = create_access_token({
            "sub": str(user.id),
            "role": user.role.value,
            "name": user.name,
            "last_name": user.last_name,
            "is_admin": False,
        })
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/admin/billing/prepay",
            headers=headers, json={"months": 12},
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["invoice_id"] > 0
        assert payload["prepay"]["amount"] == 4400
        assert payload["billing"]["prepay"]["available"] is False

        duplicate = await client.post(
            "/api/v1/admin/billing/prepay",
            headers=headers, json={"months": 12},
        )
        assert duplicate.status_code == 400
        assert "уже выставлен" in duplicate.json()["detail"].lower()

        cancelled = await client.post(
            "/api/v1/admin/billing/prepay/cancel", headers=headers,
        )
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["billing"]["prepay"]["available"] is True
        assert cancelled.json()["billing"]["invoices"][0]["status"] == "void"

        second = await client.post(
            "/api/v1/admin/billing/prepay",
            headers=headers, json={"months": 1},
        )
        assert second.status_code == 200, second.text
        assert second.json()["prepay"]["amount"] == 250

    async def test_prepay_invoice_is_not_paid_by_bonus_credits(self, session):
        from decimal import Decimal
        from app.services.billing import apply_credits, create_prepayment

        _user, mp, _account = await _mk_master(
            session, "PrepayCredit", "prepay-credit@example.com")
        session.add(BillingCredit(
            master_id=mp.id, source="manual", source_ref="manual:test",
            amount=Decimal("100"), remaining=Decimal("100"),
            expires_at=NOW + timedelta(days=90), created_at=NOW,
        ))
        await session.flush()
        invoice, _quote = await create_prepayment(session, mp.id, 1, now=NOW)
        await apply_credits(session, mp.id, now=NOW + timedelta(days=1))
        assert invoice.status == "open"
        assert float(invoice.credits_applied) == 0
        credit = (await session.execute(
            select(BillingCredit).where(BillingCredit.master_id == mp.id)
        )).scalar_one()
        assert float(credit.remaining) == 100


class TestBlockingAndPayment:
    async def test_unpaid_goes_readonly_and_payment_restores(self, session):
        from decimal import Decimal
        from app.services.billing import process_master, record_payment

        _user, mp, _account = await _mk_master(session, "Blocked", "blocked@example.com")
        result = await process_master(session, mp.id, now=NOW + timedelta(days=22))
        assert result["access_status"] == "readonly"

        invoice = (await session.execute(
            select(BillingInvoice).where(BillingInvoice.master_id == mp.id)
        )).scalar_one()
        await record_payment(
            session, invoice, amount=Decimal("250"), method="manual",
            now=NOW + timedelta(days=22),
        )
        await session.commit()
        account = (await session.execute(
            select(MasterBillingAccount).where(
                MasterBillingAccount.master_id == mp.id)
        )).scalar_one()
        assert account.access_status == "active"
        assert invoice.status == "paid"

    async def test_paused_after_30_days_overdue(self, session):
        from app.services.billing import process_master

        _user, mp, _account = await _mk_master(session, "Paused", "paused@example.com")
        result = await process_master(session, mp.id, now=NOW + timedelta(days=55))
        assert result["access_status"] == "paused"

    async def test_manual_credit_pays_invoice(self, session):
        from decimal import Decimal
        from app.services.billing import add_manual_credit, process_master

        _user, mp, _account = await _mk_master(session, "Credit", "credit@example.com")
        await process_master(session, mp.id, now=NOW + timedelta(days=16))
        await add_manual_credit(
            session, mp.id, Decimal("100"), note="test",
            now=NOW + timedelta(days=16),
        )
        await process_master(session, mp.id, now=NOW + timedelta(days=16))
        invoice = (await session.execute(
            select(BillingInvoice).where(BillingInvoice.master_id == mp.id)
        )).scalar_one()
        assert float(invoice.credits_applied) == 100
        assert float(invoice.paid_amount) == 0


class TestVisitPrompt:
    async def test_prompt_after_48h_and_inline_confirmation(self, session, engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from app.services.billing import confirm_visit, run_visit_prompts_once
        from app.utils import localnow_naive

        from app.models.review import Review

        _muser, mp, _account = await _mk_master(
            session, "Visit", "visit@example.com")
        cuser, cp = await _mk_client(session, "Client", "visit-client@example.com", "vk")
        appointment = Appointment(
            master_id=mp.id, client_id=cp.id,
            appointment_date=localnow_naive() - timedelta(days=3),
            status="completed", price=1000, duration_minutes=60,
            created_by_role="client", created_by_user_id=cuser.id,
        )
        old_appointment = Appointment(
            master_id=mp.id, client_id=cp.id,
            appointment_date=localnow_naive() - timedelta(days=30),
            status="completed", price=1000, duration_minutes=60,
            created_by_role="client", created_by_user_id=cuser.id,
        )
        reviewed_appointment = Appointment(
            master_id=mp.id, client_id=cp.id,
            appointment_date=localnow_naive() - timedelta(days=3, hours=1),
            status="completed", price=1000, duration_minutes=60,
            created_by_role="client", created_by_user_id=cuser.id,
        )
        session.add_all([appointment, old_appointment, reviewed_appointment])
        await session.flush()
        session.add(Review(
            appointment_id=reviewed_appointment.id, master_id=mp.id,
            client_name="Client", client_phone="+79990000000", rating=5,
        ))
        await session.commit()

        factory = async_sessionmaker(engine, expire_on_commit=False)
        sent = await run_visit_prompts_once(session_factory=factory)
        assert sent == 1
        notification = (await session.execute(
            select(Notification).where(
                Notification.recipient_id == cuser.id,
                Notification.kind == "visit_feedback",
            )
        )).scalar_one()
        assert notification.appointment_id == appointment.id

        result = await confirm_visit(session, cuser, appointment.id, "confirmed")
        assert result["status"] == "confirmed"
        await session.commit()
        row = (await session.execute(
            select(Appointment).where(Appointment.id == appointment.id)
        )).scalar_one()
        assert row.visit_confirmation_status == "confirmed"

    async def test_past_pending_visit_is_also_prompted(self, session, engine):
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from app.services.billing import run_visit_prompts_once
        from app.utils import localnow_naive

        _muser, mp, _account = await _mk_master(
            session, "Pending", "visit-pending@example.com")
        cuser, cp = await _mk_client(
            session, "Pending Client", "visit-pending-client@example.com", "vk")
        appointment = Appointment(
            master_id=mp.id, client_id=cp.id,
            appointment_date=localnow_naive() - timedelta(days=3),
            status="pending", price=1000, duration_minutes=60,
            created_by_role="client", created_by_user_id=cuser.id,
        )
        session.add(appointment)
        await session.commit()

        factory = async_sessionmaker(engine, expire_on_commit=False)
        sent = await run_visit_prompts_once(session_factory=factory)
        assert sent == 1
        notification = (await session.execute(
            select(Notification).where(
                Notification.recipient_id == cuser.id,
                Notification.kind == "visit_feedback",
            )
        )).scalar_one()
        assert notification.appointment_id == appointment.id


class TestPublicVisibility:
    async def test_blocked_master_disappears_from_public_list(
            self, client, session):
        from app.services.billing import process_master

        _user, mp, _account = await _mk_master(
            session, "Hidden", "hidden@example.com")
        await process_master(session, mp.id, now=NOW + timedelta(days=22))
        await session.commit()

        response = await client.get("/api/v1/masters/")
        assert response.status_code == 200
        assert all(item["id"] != mp.id for item in response.json())

        response = await client.get(f"/api/v1/masters/{mp.id}")
        assert response.status_code == 404

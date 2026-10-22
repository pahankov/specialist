"""Billing engine: trial ladder, invoices, credits, bonuses and referrals.

Money rules (manual payments, no card gateway yet):
- 14-day full trial, then invoices on day 15 / 45 / 75+ (250 / 250 / 500 ₽);
- client bonus 25 ₽ per eligible client (max 10 / 250 ₽);
- referral bonus 125 ₽ per qualified colleague (max 2 / 250 ₽);
- credits are applied oldest-invoice-first and live for 90 days;
- a master can prepay 1 month or 12 months (annual −20%). Prepayment creates
  an optional invoice outside the monthly ladder; when an admin confirms it,
  a long-lived credit is added and future monthly invoices consume it;
- unpaid monthly invoices put the cabinet into read-only after the due date
  and pause it after 30 days; a recorded payment restores access immediately.
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.database import AsyncSessionLocal
from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.billing import (
    BillingCredit,
    BillingCreditApplication,
    BillingInvoice,
    BillingPayment,
    ClientBonusAward,
    MasterBillingAccount,
    MasterReferral,
    ReferralClick,
)
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.notification import Notification
from app.models.review import Review
from app.models.user import User, UserRole
from app.services.notifications import notify_user
from app.utils import localnow_naive

logger = get_logger(__name__)

TRIAL_DAYS = 14
CLIENT_CHECK_DAY = 21
CLIENT_BONUS_RATE = Decimal("25")
CLIENT_BONUS_MAX_CLIENTS = 10
CLIENT_BONUS_MAX = Decimal("250")
REFERRAL_BONUS = Decimal("125")
REFERRAL_MAX = 2
REFERRAL_CLICK_DAYS = 60
REFERRAL_QUALIFY_BOOKINGS = 7
CREDIT_TTL_DAYS = 90
PREPAY_MONTHS = 12
PREPAY_DISCOUNT_PERCENT = 20
PREPAY_KIND_MONTH = "prepay_month"
PREPAY_KIND_YEAR = "prepay_year"
BLOCK_AFTER_DAYS = 0
PAUSE_AFTER_DAYS = 30
UNCONFIRMED_THRESHOLD = 0.30
# On rollout, do not flood clients with prompts for visits from months ago.
PROMPT_LOOKBACK_DAYS = 14

ACCESS_TRIAL = "trial"
ACCESS_ACTIVE = "active"
ACCESS_READONLY = "readonly"
ACCESS_PAUSED = "paused"
ACCESS_SUSPENDED = "suspended"

ACCESS_LABELS = {
    ACCESS_TRIAL: "Пробный период",
    ACCESS_ACTIVE: "Активен",
    ACCESS_READONLY: "Только чтение",
    ACCESS_PAUSED: "Приостановлен",
    ACCESS_SUSPENDED: "Заблокирован администратором",
}

INVOICE_LABELS = {
    "open": "К оплате",
    "paid": "Оплачен",
    "void": "Отменён",
}

CREDIT_LABELS = {
    "client_bonus": "Бонус за клиентов",
    "referral_bonus": "Бонус за реферала",
    "manual": "Ручное начисление",
    "prepayment": "Предоплата",
}

REFERRAL_LABELS = {
    "pending": "Проверяется",
    "qualified": "Зачтён",
    "rejected": "Не зачтён",
}

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _due(invoice: BillingInvoice) -> Decimal:
    if invoice.status in ("paid", "void"):
        return Decimal("0")
    return max(
        Decimal("0"),
        _money(invoice.amount) - _money(invoice.credits_applied)
        - _money(invoice.paid_amount),
    )


def _is_prepay(invoice: BillingInvoice) -> bool:
    """Prepayment invoices are optional top-ups, not monthly debt."""
    return (invoice.kind or "monthly") != "monthly"


def _normal_invoices(invoices: list[BillingInvoice]) -> list[BillingInvoice]:
    return [invoice for invoice in invoices if not _is_prepay(invoice)]


def _next_period_index(invoices: list[BillingInvoice]) -> int:
    """Next monthly ladder index; negative prepayment rows are ignored."""
    return max(
        (invoice.period_index for invoice in invoices
         if invoice.period_index > 0),
        default=0,
    ) + 1


def _iso(value: Optional[datetime]) -> Optional[str]:
    value = _aware(value)
    return value.isoformat() if value else None


def social_providers(user: User) -> set[str]:
    """Bound social providers. One client may only have several for bonuses."""
    providers: set[str] = set()
    if getattr(user, "vk_user_id", None):
        providers.add("vk")
    if getattr(user, "yandex_user_id", None):
        providers.add("yandex")
    if getattr(user, "max_user_id", None):
        providers.add("max")
    return providers


def has_social(user: User) -> bool:
    return bool(social_providers(user))


def is_billable_master(master: MasterProfile) -> bool:
    """Only real master accounts take part in billing.

    Admins keep a MasterProfile for tools but are never billed. Client drafts
    are not masters yet: they start their trial only when activated and the
    role becomes MASTER.
    """
    return master is not None and (
        master.user is not None and master.user.role == UserRole.MASTER
    )


def _new_referral_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(8))


async def _unique_referral_code(db: AsyncSession) -> str:
    for _ in range(30):
        code = _new_referral_code()
        taken = (await db.execute(
            select(MasterBillingAccount.id).where(
                MasterBillingAccount.referral_code == code)
        )).scalar_one_or_none()
        if not taken:
            return code
    # Practically unreachable; keep the flow deterministic for tests.
    return secrets.token_hex(8).upper()


async def ensure_account(
    db: AsyncSession,
    master: MasterProfile,
    now: Optional[datetime] = None,
) -> MasterBillingAccount:
    """Return the billing account, creating it from the profile trial dates."""
    now = _aware(now) or _now()
    account = (await db.execute(
        select(MasterBillingAccount).where(
            MasterBillingAccount.master_id == master.id)
    )).scalar_one_or_none()
    if account is not None:
        # Admin may have changed trial_ends_at in the legacy master form.
        # Sync only while no invoice exists, otherwise history would shift.
        profile_end = _aware(master.trial_ends_at)
        if profile_end and profile_end != _aware(account.trial_ends_at):
            invoice_exists = (await db.execute(
                select(BillingInvoice.id).where(
                    BillingInvoice.master_id == master.id).limit(1)
            )).scalar_one_or_none()
            if not invoice_exists:
                account.trial_ends_at = profile_end
                account.trial_started_at = profile_end - timedelta(days=TRIAL_DAYS)
                account.billing_started_at = account.trial_started_at
        return account

    trial_end = _aware(master.trial_ends_at) or (now + timedelta(days=TRIAL_DAYS))
    trial_start = trial_end - timedelta(days=TRIAL_DAYS)
    account = MasterBillingAccount(
        master_id=master.id,
        trial_started_at=trial_start,
        trial_ends_at=trial_end,
        billing_started_at=trial_start,
        referral_code=await _unique_referral_code(db),
        access_status=ACCESS_TRIAL,
        review_flag=False,
        created_at=now,
        updated_at=now,
    )
    db.add(account)
    await db.flush()
    return account


async def start_master_trial(
    db: AsyncSession,
    master: MasterProfile,
    now: Optional[datetime] = None,
) -> MasterBillingAccount:
    """Fresh 14-day trial at the moment a master is activated."""
    now = _aware(now) or _now()
    account = await ensure_account(db, master, now=now)
    has_invoice = (await db.execute(
        select(BillingInvoice.id).where(
            BillingInvoice.master_id == master.id).limit(1)
    )).scalar_one_or_none()
    if has_invoice is not None:
        # Re-activation of an existing master must not mint a fresh trial.
        return account
    account.trial_started_at = now
    account.trial_ends_at = now + timedelta(days=TRIAL_DAYS)
    account.billing_started_at = now
    account.access_status = ACCESS_TRIAL
    account.review_flag = False
    account.bonus_blocked_until = None
    account.last_processed_at = None
    master.trial_ends_at = account.trial_ends_at
    master.tariff = "trial"
    await db.flush()
    return account


async def link_referral_to_master(
    db: AsyncSession, user: User, master: MasterProfile,
) -> Optional[MasterReferral]:
    """Attach an already-attributed referral to the newly activated profile."""
    referral = (await db.execute(
        select(MasterReferral).where(
            MasterReferral.referred_user_id == user.id)
    )).scalar_one_or_none()
    if referral is None:
        return None
    if referral.referred_master_id is None:
        referral.referred_master_id = master.id
        await db.flush()
    return referral


async def resume_master_billing(
    db: AsyncSession,
    user: User,
    master: MasterProfile,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """Apply activation/re-activation billing rules and refresh access.

    A fresh 14-day trial starts only while no invoice exists. An existing
    master keeps their payment history; access is recalculated immediately so
    an admin does not have to wait for the 15-minute background tick.
    """
    if user.role != UserRole.MASTER:
        return None
    await start_master_trial(db, master, now=now)
    await link_referral_to_master(db, user, master)
    return await process_master(db, master.id, now=now, notify=False)


# ─── Referral links / attribution ─────────────────────────────────────

async def create_referral_click(
    db: AsyncSession, code: str, now: Optional[datetime] = None,
) -> Optional[dict]:
    """Record a /r/<code> click and return a short-lived attribution token."""
    now = _aware(now) or _now()
    account = (await db.execute(
        select(MasterBillingAccount).where(
            MasterBillingAccount.referral_code == code.upper())
    )).scalar_one_or_none()
    if account is None:
        return None
    master = (await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == account.master_id)
    )).scalar_one_or_none()
    if (master is None or not is_billable_master(master)
            or master.user.role != UserRole.MASTER):
        return None
    token = secrets.token_urlsafe(32)
    click = ReferralClick(
        master_id=master.id,
        token=token,
        clicked_at=now,
        expires_at=now + timedelta(days=REFERRAL_CLICK_DAYS),
    )
    db.add(click)
    await db.flush()
    return {
        "token": token,
        "expires_at": click.expires_at.isoformat(),
        "master_name": master.user.name or "Мастер",
        "referral_code": account.referral_code,
    }


async def attribute_referral(
    db: AsyncSession,
    user: User,
    click_token: str,
    now: Optional[datetime] = None,
) -> dict:
    """Bind a logged-in user to the master whose link they clicked."""
    now = _aware(now) or _now()
    click = (await db.execute(
        select(ReferralClick).where(ReferralClick.token == click_token)
    )).scalar_one_or_none()
    if click is None:
        return {"status": "invalid", "reason": "Ссылка не найдена"}
    if click.used_by_user_id is not None and click.used_by_user_id != user.id:
        return {"status": "invalid", "reason": "Ссылка уже использована"}

    existing = (await db.execute(
        select(MasterReferral).where(MasterReferral.referred_user_id == user.id)
    )).scalar_one_or_none()
    if existing is not None:
        if click.used_by_user_id is None:
            click.used_by_user_id = user.id
            click.used_at = now
        return {"status": existing.status, "referral_id": existing.id,
                "reason": existing.reject_reason}

    if _aware(click.expires_at) <= now:
        return {"status": "expired", "reason": "Срок ссылки истёк"}

    referrer = (await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == click.master_id)
    )).scalar_one_or_none()
    if (referrer is None or not is_billable_master(referrer)
            or referrer.user.role != UserRole.MASTER):
        return {"status": "invalid", "reason": "Мастер не найден"}
    if referrer.user_id == user.id:
        return {"status": "rejected", "reason": "Нельзя пригласить самого себя"}

    # B may be an existing client, but must be new to the master role.
    own_master = (await db.execute(
        select(MasterProfile).where(MasterProfile.user_id == user.id)
    )).scalar_one_or_none()
    if own_master is not None and (
            own_master.status == "active" or user.role == UserRole.MASTER):
        return {"status": "rejected", "reason": "Вы уже являетесь мастером"}

    referrer_code = (await db.execute(
        select(MasterBillingAccount.referral_code).where(
            MasterBillingAccount.master_id == referrer.id)
    )).scalar_one_or_none()
    referral = MasterReferral(
        referrer_master_id=referrer.id,
        referred_user_id=user.id,
        referred_master_id=own_master.id if own_master is not None else None,
        code=referrer_code or "",
        clicked_at=click.clicked_at,
        registered_at=now,
        status="pending",
        created_at=now,
    )
    db.add(referral)
    click.used_by_user_id = user.id
    click.used_at = now
    await db.flush()
    return {"status": "pending", "referral_id": referral.id}


# ─── Candidate bookings ───────────────────────────────────────────────

async def _candidate_rows(
    db: AsyncSession,
    master_id: int,
    start: datetime,
    end: datetime,
    *,
    referral_rules: bool = False,
) -> list[dict]:
    """Client-created, social-verified, >=500 ₽ bookings in the trial window."""
    rows = (await db.execute(
        select(Appointment, User)
        .join(ClientProfile, Appointment.client_id == ClientProfile.id)
        .join(User, ClientProfile.user_id == User.id)
        .where(
            Appointment.master_id == master_id,
            Appointment.created_by_role == "client",
            Appointment.status.notin_(("cancelled", "no_show")),
            Appointment.price.is_not(None),
            Appointment.price >= 500,
            Appointment.created_at.is_not(None),
            Appointment.created_at >= start,
            Appointment.created_at <= end,
            or_(
                Appointment.visit_confirmation_status.is_(None),
                Appointment.visit_confirmation_status != "disputed",
            ),
        )
        .order_by(Appointment.created_at.asc(), Appointment.id.asc())
    )).all()

    candidates: list[dict] = []
    per_client: dict[int, int] = {}
    per_client_days: dict[int, set[date]] = {}
    for appointment, client_user in rows:
        if not has_social(client_user):
            continue
        count = per_client.get(appointment.client_id, 0)
        if count >= 2:
            continue
        day = _aware(appointment.appointment_date)
        day_key = day.date() if day else None
        if referral_rules and day_key in per_client_days.get(appointment.client_id, set()):
            continue
        per_client[appointment.client_id] = count + 1
        if day_key:
            per_client_days.setdefault(appointment.client_id, set()).add(day_key)
        candidates.append({
            "appointment": appointment,
            "client_user": client_user,
            "client_id": appointment.client_id,
            "day": day_key,
        })

    # No more than three bonus bookings on the same day for one master.
    per_day: dict[date, int] = {}
    limited: list[dict] = []
    for item in candidates:
        day_key = item["day"]
        if day_key is not None and per_day.get(day_key, 0) >= 3:
            continue
        if day_key is not None:
            per_day[day_key] = per_day.get(day_key, 0) + 1
        limited.append(item)
    return limited


async def _prompted_visit_stats(
    db: AsyncSession, master_id: int, start: datetime, end: datetime,
) -> tuple[int, int]:
    """All prompted visits in the trial window, not only bonus candidates.

    A master cannot hide unreliable visits by keeping them cheap or by
    serving clients without a linked social account: the >30% quality
    filter looks at every prompted visit of the month.
    """
    rows = (await db.execute(
        select(Appointment.visit_confirmation_status)
        .where(
            Appointment.master_id == master_id,
            Appointment.visit_prompt_sent_at.is_not(None),
            Appointment.appointment_date >= start,
            Appointment.appointment_date <= end,
        )
    )).scalars().all()
    prompted = len(rows)
    unconfirmed = sum(
        1 for status in rows if (status or "pending") != "confirmed")
    return prompted, unconfirmed


async def _claimed_by_other_master(
    db: AsyncSession, client_id: int, appointment: Appointment,
    master_id: int,
) -> bool:
    """One client can earn a bonus for only one master: the earliest claim."""
    earlier = (await db.execute(
        select(Appointment.id)
        .join(MasterBillingAccount,
              Appointment.master_id == MasterBillingAccount.master_id)
        .where(
            Appointment.client_id == client_id,
            Appointment.master_id != master_id,
            Appointment.created_by_role == "client",
            Appointment.status.notin_(("cancelled", "no_show")),
            Appointment.price.is_not(None),
            Appointment.price >= 500,
            Appointment.created_at.is_not(None),
            or_(
                Appointment.visit_confirmation_status.is_(None),
                Appointment.visit_confirmation_status != "disputed",
            ),
            or_(
                Appointment.created_at < appointment.created_at,
                and_(
                    Appointment.created_at == appointment.created_at,
                    Appointment.id < appointment.id,
                ),
            ),
            Appointment.created_at >= MasterBillingAccount.trial_started_at,
            Appointment.created_at <= MasterBillingAccount.trial_ends_at,
        )
        .limit(1)
    )).scalar_one_or_none()
    return earlier is not None


async def compute_client_bonus(
    db: AsyncSession,
    master_id: int,
    account: MasterBillingAccount,
    now: Optional[datetime] = None,
) -> dict:
    now = _aware(now) or _now()
    rows = await _candidate_rows(
        db, master_id, _aware(account.trial_started_at),
        _aware(account.trial_ends_at),
    )
    filtered: list[dict] = []
    for item in rows:
        if await _claimed_by_other_master(
                db, item["client_id"], item["appointment"], master_id):
            continue
        filtered.append(item)

    prompted, unconfirmed = await _prompted_visit_stats(
        db, master_id, _aware(account.trial_started_at),
        _aware(account.trial_ends_at),
    )
    ratio = (unconfirmed / prompted) if prompted else 0.0
    # 25 ₽ is paid per unique client, not per booking: a client's second
    # booking proves the visit but must not double the bonus. Keep the first
    # qualifying booking as the evidence for that client.
    seen_clients: set[int] = set()
    eligible: list[dict] = []
    for item in filtered:
        if (item["appointment"].visit_confirmation_status or "pending") == "disputed":
            continue
        if item["client_id"] in seen_clients:
            continue
        seen_clients.add(item["client_id"])
        eligible.append(item)
    count = min(len(eligible), CLIENT_BONUS_MAX_CLIENTS)
    return {
        "eligible_count": count,
        "total_candidates": len(filtered),
        "amount": _money(Decimal(count) * CLIENT_BONUS_RATE),
        "unconfirmed_count": unconfirmed,
        "prompted_count": prompted,
        "unconfirmed_ratio": round(ratio, 4),
        "review_flag": ratio > UNCONFIRMED_THRESHOLD,
        "appointment_ids": [item["appointment"].id for item in eligible[:count]],
    }


async def evaluate_client_bonus(
    db: AsyncSession,
    master: MasterProfile,
    account: MasterBillingAccount,
    now: Optional[datetime] = None,
) -> ClientBonusAward:
    now = _aware(now) or _now()
    existing = (await db.execute(
        select(ClientBonusAward).where(
            ClientBonusAward.master_id == master.id)
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    calc = await compute_client_bonus(db, master.id, account, now=now)
    flagged = bool(calc["review_flag"])
    if flagged:
        account.review_flag = True
        # Quality filter blocks future bonuses, not this month's earned bonus.
        account.bonus_blocked_until = now + timedelta(days=CREDIT_TTL_DAYS)

    blocked = bool(
        (account.review_flag or (
            account.bonus_blocked_until
            and _aware(account.bonus_blocked_until) > now))
    ) and not flagged  # a fresh >30% flag still keeps month 1
    status = "blocked" if blocked else (
        "credited" if calc["amount"] > 0 else "rejected")
    award = ClientBonusAward(
        master_id=master.id,
        trial_started_at=_aware(account.trial_started_at),
        trial_ends_at=_aware(account.trial_ends_at),
        eligible_count=calc["eligible_count"],
        max_count=CLIENT_BONUS_MAX_CLIENTS,
        amount=calc["amount"],
        status=status,
        total_candidates=calc["total_candidates"],
        unconfirmed_count=calc["unconfirmed_count"],
        review_flagged=flagged,
        details={
            "appointment_ids": calc["appointment_ids"],
            "prompted_count": calc["prompted_count"],
            "unconfirmed_ratio": calc["unconfirmed_ratio"],
        },
        evaluated_at=now,
        created_at=now,
    )
    db.add(award)
    await db.flush()

    if calc["amount"] > 0 and not blocked:
        db.add(BillingCredit(
            master_id=master.id,
            source="client_bonus",
            source_ref=f"client-bonus:{award.id}",
            amount=calc["amount"],
            remaining=calc["amount"],
            expires_at=now + timedelta(days=CREDIT_TTL_DAYS),
            note=f"Бонус за {calc['eligible_count']} клиентов",
            created_at=now,
        ))
        await db.flush()
        await notify_user(
            db, master.user_id,
            f"Бонус за клиентов: {calc['eligible_count']} × 25 ₽ = "
            f"{_fmt_money(calc['amount'])}.\n"
            "Сумма зачтена в счёт оплаты или сохранена как кредит на 90 дней.",
            audience="system", kind="billing_bonus", link="billing",
        )
    if flagged:
        await notify_user(
            db, master.user_id,
            "Проверка качества: более 30% визитов не подтверждены клиентами.\n"
            "Бонус за текущий месяц сохранён, но начисления будущих бонусов "
            "приостановлены до проверки администратором.",
            audience="system", kind="billing_review", link="billing",
        )
    return award


# ─── Referrals ────────────────────────────────────────────────────────

async def _referral_qualified_count(
    db: AsyncSession, referred_master_id: int,
) -> list[dict]:
    account = (await db.execute(
        select(MasterBillingAccount).where(
            MasterBillingAccount.master_id == referred_master_id)
    )).scalar_one_or_none()
    if account is None:
        return []
    return await _candidate_rows(
        db, referred_master_id,
        _aware(account.trial_started_at), _aware(account.trial_ends_at),
        referral_rules=True,
    )


async def evaluate_referrals_for_master(
    db: AsyncSession, master: MasterProfile, now: Optional[datetime] = None,
) -> list[MasterReferral]:
    """Evaluate pending referrals where this master is the referred one."""
    now = _aware(now) or _now()
    account = await ensure_account(db, master, now=now)
    if now < _aware(account.trial_started_at) + timedelta(days=CLIENT_CHECK_DAY):
        return []

    referrals = (await db.execute(
        select(MasterReferral).where(
            MasterReferral.referred_master_id == master.id,
            MasterReferral.status == "pending",
        )
    )).scalars().all()
    results: list[MasterReferral] = []
    for referral in referrals:
        referrer = (await db.execute(
            select(MasterProfile)
            .options(joinedload(MasterProfile.user))
            .where(MasterProfile.id == referral.referrer_master_id)
        )).scalar_one_or_none()
        referred_user = (await db.execute(
            select(User).where(User.id == referral.referred_user_id)
        )).scalar_one_or_none()
        if referrer is None or referrer.user is None or referred_user is None:
            referral.status = "rejected"
            referral.reject_reason = "Участник реферала не найден"
            referral.evaluated_at = now
            results.append(referral)
            continue
        if not is_billable_master(referrer):
            referral.status = "rejected"
            referral.reject_reason = "Реферер больше не является мастером"
            referral.evaluated_at = now
            results.append(referral)
            continue

        a_social = social_providers(referrer.user)
        b_social = social_providers(referred_user)
        reason = None
        if not a_social or not b_social:
            reason = "У участников не привязана социальная сеть"
        elif a_social & b_social:
            reason = "Социальные сети участников совпадают"

        candidates = await _referral_qualified_count(db, master.id)
        referral.qualified_count = len(candidates)
        qualified = reason is None and len(candidates) >= REFERRAL_QUALIFY_BOOKINGS

        if qualified:
            already = (await db.execute(
                select(func.count(MasterReferral.id)).where(
                    MasterReferral.referrer_master_id == referrer.id,
                    MasterReferral.status == "qualified",
                )
            )).scalar() or 0
            if already >= REFERRAL_MAX:
                qualified = False
                reason = f"Достигнут лимит {REFERRAL_MAX} реферала"

        referral.evaluated_at = now
        if not qualified:
            referral.status = "rejected"
            referral.reject_reason = reason or (
                f"Нужно {REFERRAL_QUALIFY_BOOKINGS} записей, "
                f"засчитано {len(candidates)}"
            )
            results.append(referral)
            continue

        referral.status = "qualified"
        referral.amount = REFERRAL_BONUS
        db.add(BillingCredit(
            master_id=referrer.id,
            source="referral_bonus",
            source_ref=f"referral:{referral.id}",
            amount=REFERRAL_BONUS,
            remaining=REFERRAL_BONUS,
            expires_at=now + timedelta(days=CREDIT_TTL_DAYS),
            note=f"Реферал: {referred_user.name or 'коллега'}",
            created_at=now,
        ))
        await db.flush()
        await notify_user(
            db, referrer.user_id,
            f"Реферальный бонус: {_fmt_money(REFERRAL_BONUS)} за коллегу "
            f"{referred_user.name or ''}. Сумма зачтена в счёт оплаты "
            "или сохранена как кредит на 90 дней.",
            audience="system", kind="billing_bonus", link="billing",
        )
        await apply_credits(db, referrer.id, now=now)
        results.append(referral)
    await db.flush()
    return results


# ─── Ledger / invoices ────────────────────────────────────────────────

def _invoice_terms(
    account: MasterBillingAccount, period_index: int,
) -> tuple[datetime, datetime, datetime, Decimal]:
    trial_end = _aware(account.trial_ends_at)
    # Trial covers days 0–14; the first invoice lands on day 15 and is due
    # on day 21 (the same checkpoint used for client bonuses).
    issue_at = trial_end + timedelta(days=1 + 30 * (period_index - 1))
    due_at = issue_at + timedelta(days=6)
    amount = Decimal("250") if period_index <= 2 else Decimal("500")
    return issue_at, due_at, due_at, amount


class BillingValidationError(ValueError):
    """A user-facing billing rule was violated (router turns it into 400)."""


def _prepayment_quote(
    account: MasterBillingAccount,
    invoices: list[BillingInvoice],
    credits: list[BillingCredit],
    months: int,
    now: datetime,
) -> dict:
    """Quote a monthly/annual prepayment without changing the ledger.

    The price is the sum of the next N monthly invoices. Only the annual
    option gets the 20% discount. A prepayment is optional: it does not
    affect access and does not replace the normal monthly ladder until the
    admin confirms the payment and the credit is created.
    """
    if months not in (1, PREPAY_MONTHS):
        raise BillingValidationError("Можно оплатить 1 или 12 месяцев")

    next_index = _next_period_index(invoices)
    amounts = [
        _invoice_terms(account, index)[3]
        for index in range(next_index, next_index + months)
    ]
    base_amount = _money(sum(amounts, Decimal("0")))
    discount = PREPAY_DISCOUNT_PERCENT if months == PREPAY_MONTHS else 0
    amount = _money(
        base_amount * (Decimal("100") - Decimal(discount)) / Decimal("100")
    )
    starts_at = _invoice_terms(account, next_index)[0]
    ends_at = _invoice_terms(
        account, next_index + months - 1)[0] + timedelta(days=30)

    open_normal = [
        invoice for invoice in _normal_invoices(invoices)
        if invoice.status == "open" and _due(invoice) > 0
    ]
    open_prepay = next(
        (invoice for invoice in invoices
         if _is_prepay(invoice) and invoice.status == "open"),
        None,
    )
    active_prepay = next(
        (credit for credit in credits
         if credit.source == "prepayment"
         and _money(credit.remaining) > 0
         and (credit.expires_at is None
              or _aware(credit.expires_at) > now)),
        None,
    )

    reason = None
    if open_normal:
        reason = "Сначала оплатите текущий счёт"
    elif open_prepay is not None:
        reason = "Счёт на предоплату уже выставлен"
    elif active_prepay is not None:
        reason = "Предоплата уже действует"

    return {
        "months": months,
        "base_amount": float(base_amount),
        "amount": float(amount),
        "discount_percent": discount,
        "starts_at": _iso(starts_at),
        "ends_at": _iso(ends_at),
        "period_index": next_index,
        "available": reason is None,
        "reason": reason,
        "open_invoice_id": open_prepay.id if open_prepay else None,
        "prepaid_until": _iso(account.prepaid_until) if active_prepay else None,
    }


async def create_prepayment(
    db: AsyncSession, master_id: int, months: int,
    now: Optional[datetime] = None,
) -> tuple[BillingInvoice, dict]:
    """Create an optional prepayment invoice (outside the monthly ladder)."""
    now = _aware(now) or _now()
    await process_master(db, master_id, now=now, notify=False)
    master = (await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )).scalar_one_or_none()
    if master is None or not is_billable_master(master):
        raise BillingValidationError("Мастер не найден")
    account = await ensure_account(db, master, now=now)
    invoices = (await db.execute(
        select(BillingInvoice).where(BillingInvoice.master_id == master_id)
    )).scalars().all()
    credits = (await db.execute(
        select(BillingCredit).where(BillingCredit.master_id == master_id)
    )).scalars().all()
    quote = _prepayment_quote(account, invoices, credits, months, now)
    if not quote["available"]:
        raise BillingValidationError(quote["reason"] or "Предоплата недоступна")

    next_index = quote["period_index"]
    starts_at = _invoice_terms(account, next_index)[0]
    last_issue = _invoice_terms(account, next_index + months - 1)[0]
    ends_at = last_issue + timedelta(days=30)
    due_at = max(now, starts_at) + timedelta(days=6)
    kind = PREPAY_KIND_YEAR if months == PREPAY_MONTHS else PREPAY_KIND_MONTH
    negative_index = min(
        (invoice.period_index for invoice in invoices
         if invoice.period_index < 0),
        default=0,
    ) - 1
    note = (
        f"Предоплата {months} мес. Базовая стоимость "
        f"{_fmt_money(quote['base_amount'])}"
        + (f", скидка {PREPAY_DISCOUNT_PERCENT}%, "
           f"к оплате {_fmt_money(quote['amount'])}."
           if months == PREPAY_MONTHS else ".")
    )
    invoice = BillingInvoice(
        master_id=master_id,
        period_index=negative_index,
        amount=_money(quote["amount"]),
        base_amount=_money(quote["base_amount"]),
        credits_applied=Decimal("0"),
        paid_amount=Decimal("0"),
        kind=kind,
        months=months,
        status="open",
        issue_at=now,
        due_at=due_at,
        block_at=due_at,
        period_start=starts_at,
        period_end=ends_at,
        note=note,
        created_at=now,
        updated_at=now,
    )
    db.add(invoice)
    await db.flush()

    body = (
        f"Счёт на предоплату {months} мес.: {_fmt_money(quote['amount'])}"
        + (f" (скидка {PREPAY_DISCOUNT_PERCENT}% от "
           f"{_fmt_money(quote['base_amount'])})"
           if months == PREPAY_MONTHS else "")
        + ".\nОплата подтверждается администратором вручную — после "
        "подтверждения сумма будет зачислена на баланс и автоматически "
        "закроет следующие счета."
    )
    await notify_user(
        db, master.user_id, body,
        audience="system", kind="billing_prepay", link="billing",
    )
    # The superadmin sees the request in the bell and can confirm it in the
    # master's billing tab. Support already uses the same admin fan-out.
    admin_ids = (await db.execute(
        select(User.id).where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
    )).scalars().all()
    for admin_id in admin_ids:
        await notify_user(
            db, admin_id,
            f"Мастер {master.user.name or 'без имени'} запросил предоплату "
            f"на {months} мес.: {_fmt_money(quote['amount'])}.\n"
            "Подтвердите оплату в биллинге мастера.",
            audience="support", kind="billing_prepay", link="billing",
        )
    await db.flush()
    return invoice, quote


async def expire_credits(
    db: AsyncSession, master_id: int, now: Optional[datetime] = None,
) -> None:
    now = _aware(now) or _now()
    credits = (await db.execute(
        select(BillingCredit).where(
            BillingCredit.master_id == master_id,
            BillingCredit.remaining > 0,
        )
    )).scalars().all()
    for credit in credits:
        if credit.expires_at and _aware(credit.expires_at) <= now:
            credit.remaining = Decimal("0")
            credit.expired_at = now


async def apply_credits(
    db: AsyncSession, master_id: int, now: Optional[datetime] = None,
) -> Decimal:
    """Apply available credits to the oldest open invoices, FIFO."""
    now = _aware(now) or _now()
    await expire_credits(db, master_id, now=now)
    credits = (await db.execute(
        select(BillingCredit).where(
            BillingCredit.master_id == master_id,
            BillingCredit.remaining > 0,
        )
    )).scalars().all()
    credits = sorted(
        credits,
        key=lambda c: (
            {"client_bonus": 0, "referral_bonus": 1, "manual": 2}.get(c.source, 3),
            _aware(c.expires_at) or datetime.max.replace(tzinfo=timezone.utc),
            c.id,
        ),
    )
    invoices = (await db.execute(
        select(BillingInvoice).where(
            BillingInvoice.master_id == master_id,
            BillingInvoice.status == "open",
            # Prepayment invoices are optional top-ups: bonuses and credits
            # must never close them, otherwise a prepayment credit would be
            # granted without a real payment.
            func.coalesce(BillingInvoice.kind, "monthly") == "monthly",
        ).order_by(BillingInvoice.period_index.asc())
    )).scalars().all()

    applied = Decimal("0")
    for invoice in invoices:
        due = _due(invoice)
        if due <= 0:
            continue
        for credit in credits:
            if credit.remaining <= 0:
                continue
            piece = min(due, _money(credit.remaining))
            if piece <= 0:
                continue
            # One row per (credit, invoice) keeps the ledger readable.
            existing = (await db.execute(
                select(BillingCreditApplication).where(
                    BillingCreditApplication.credit_id == credit.id,
                    BillingCreditApplication.invoice_id == invoice.id,
                )
            )).scalar_one_or_none()
            if existing is None:
                db.add(BillingCreditApplication(
                    credit_id=credit.id, invoice_id=invoice.id,
                    amount=piece, created_at=now,
                ))
            else:
                existing.amount = _money(existing.amount) + piece
            credit.remaining = _money(credit.remaining) - piece
            invoice.credits_applied = _money(invoice.credits_applied) + piece
            due -= piece
            applied += piece
            if due <= 0:
                break
        if _due(invoice) <= 0:
            invoice.status = "paid"
            invoice.paid_at = invoice.paid_at or now
            invoice.payment_method = invoice.payment_method or "credit"
    await db.flush()
    return applied


async def _ensure_invoices(
    db: AsyncSession, master: MasterProfile, account: MasterBillingAccount,
    now: datetime,
) -> list[BillingInvoice]:
    trial_end = _aware(account.trial_ends_at)
    first_issue = trial_end + timedelta(days=1)
    if now < first_issue:
        return []
    max_index = 1 + max(0, (now - first_issue).days // 30)
    existing = (await db.execute(
        select(BillingInvoice).where(BillingInvoice.master_id == master.id)
    )).scalars().all()
    by_index = {inv.period_index: inv for inv in existing}
    created: list[BillingInvoice] = []
    for index in range(1, max_index + 1):
        if index in by_index:
            continue
        issue_at, due_at, block_at, amount = _invoice_terms(account, index)
        invoice = BillingInvoice(
            master_id=master.id, period_index=index, amount=amount,
            credits_applied=Decimal("0"), paid_amount=Decimal("0"),
            status="open", issue_at=issue_at, due_at=due_at, block_at=block_at,
            period_start=issue_at, period_end=issue_at + timedelta(days=30),
            created_at=now, updated_at=now,
        )
        db.add(invoice)
        created.append(invoice)
        by_index[index] = invoice
        await notify_user(
            db, master.user_id,
            f"Счёт за {index}-й месяц: {_fmt_money(amount)}.\n"
            f"Оплатить до {due_at.strftime('%d.%m.%Y')}. "
            "Оплата подтверждается администратором в личном кабинете.",
            audience="system", kind="billing_invoice", link="billing",
        )
        invoice.notified_at = now
    await db.flush()
    return created


async def process_master(
    db: AsyncSession,
    master_id: int,
    now: Optional[datetime] = None,
    *,
    notify: bool = True,
) -> Optional[dict]:
    """Run the whole billing tick for one master. Idempotent."""
    now = _aware(now) or _now()
    master = (await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )).scalar_one_or_none()
    if master is None or not is_billable_master(master):
        return None
    account = await ensure_account(db, master, now=now)
    # Deactivated masters are not billed. Reactivation starts a fresh trial
    # only while no invoice exists; otherwise history is recalculated.
    if master.is_active is False:
        previous_status = account.access_status
        account.access_status = ACCESS_SUSPENDED
        master.trial_ends_at = account.trial_ends_at
        await db.flush()
        return {
            "master_id": master.id,
            "access_status": ACCESS_SUSPENDED,
            "previous_status": previous_status,
            "trial_ends_at": _iso(account.trial_ends_at),
        }
    previous_status = account.access_status

    await _ensure_invoices(db, master, account, now)
    await apply_credits(db, master.id, now=now)

    # Client bonus is evaluated once, on day 21.
    if now >= _aware(account.trial_ends_at) + timedelta(days=7):
        await evaluate_client_bonus(db, master, account, now=now)
        await apply_credits(db, master.id, now=now)

    # Referral bonus for this master as the invited colleague (day 21 of B).
    await evaluate_referrals_for_master(db, master, now=now)

    invoices = (await db.execute(
        select(BillingInvoice).where(
            BillingInvoice.master_id == master.id,
            BillingInvoice.status == "open",
        )
    )).scalars().all()
    # A pending prepayment invoice is optional and never blocks the cabinet:
    # access is controlled only by the normal monthly ladder.
    monthly_open = _normal_invoices(invoices)
    overdue = [inv for inv in monthly_open
               if _due(inv) > 0 and now >= _aware(inv.block_at)]
    if now < _aware(account.trial_ends_at):
        status = ACCESS_TRIAL
    elif overdue:
        oldest = min(_aware(inv.block_at) for inv in overdue)
        days = max(0, (now - oldest).days)
        status = ACCESS_PAUSED if days >= PAUSE_AFTER_DAYS else ACCESS_READONLY
    else:
        status = ACCESS_ACTIVE

    if master.status == "suspended" or master.is_active is False:
        status = ACCESS_SUSPENDED
    account.access_status = status
    account.last_processed_at = now
    master.tariff = "trial" if status == ACCESS_TRIAL else "basic"
    master.trial_ends_at = account.trial_ends_at

    if notify:
        for invoice in overdue:
            days_overdue = max(0, (now - _aware(invoice.block_at)).days)
            if invoice.overdue_notified_at is None:
                await notify_user(
                    db, master.user_id,
                    f"Счёт за {invoice.period_index}-й месяц "
                    f"({_fmt_money(_due(invoice))}) просрочен.\n"
                    "Кабинет переведён в режим чтения. Оплата разблокирует "
                    "его в тот же день.",
                    audience="system", kind="billing_overdue", link="billing",
                )
                invoice.overdue_notified_at = now
            if days_overdue >= 3 and invoice.reminder_sent_at is None:
                await notify_user(
                    db, master.user_id,
                    f"Напоминание: счёт за {invoice.period_index}-й месяц "
                    f"({_fmt_money(_due(invoice))}) всё ещё не оплачен.\n"
                    "Доступ к кабинету остаётся только для чтения.",
                    audience="system", kind="billing_reminder", link="billing",
                )
                invoice.reminder_sent_at = now
        if previous_status != status and status in (ACCESS_READONLY, ACCESS_PAUSED):
            await notify_user(
                db, master.user_id,
                ("Кабинет приостановлен: счёт не оплачен более 30 дней."
                 if status == ACCESS_PAUSED else
                 "Кабинет работает в режиме чтения: оплатите счёт, "
                 "чтобы снова принимать записи."),
                audience="system", kind="billing_access", link="billing",
            )
        if previous_status in (ACCESS_READONLY, ACCESS_PAUSED) \
                and status == ACCESS_ACTIVE:
            await notify_user(
                db, master.user_id,
                "Оплата получена — кабинет снова активен. Спасибо!",
                audience="system", kind="billing_access", link="billing",
            )
    await db.flush()
    return {
        "master_id": master.id,
        "access_status": status,
        "previous_status": previous_status,
        "trial_ends_at": _iso(account.trial_ends_at),
    }


async def _grant_prepayment_credit(
    db: AsyncSession, invoice: BillingInvoice, now: datetime,
) -> Optional[BillingCredit]:
    """Turn a fully paid prepayment invoice into a long-lived credit."""
    if not _is_prepay(invoice) or invoice.status != "paid":
        return None
    existing = (await db.execute(
        select(BillingCredit).where(
            BillingCredit.source == "prepayment",
            BillingCredit.source_ref == f"prepay:{invoice.id}",
        )
    )).scalar_one_or_none()
    if existing is not None:
        return existing

    master = (await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == invoice.master_id)
    )).scalar_one_or_none()
    if master is None or not is_billable_master(master):
        return None
    account = await ensure_account(db, master, now=now)
    months = max(1, int(invoice.months or 1))
    amount = _money(invoice.base_amount or invoice.amount)
    if amount <= 0:
        return None
    period_end = _aware(invoice.period_end) or (
        now + timedelta(days=30 * months))
    credit = BillingCredit(
        master_id=invoice.master_id,
        source="prepayment",
        source_ref=f"prepay:{invoice.id}",
        amount=amount,
        remaining=amount,
        # The prepayment credit must live through the entire covered period
        # plus the regular 90-day grace window.
        expires_at=period_end + timedelta(days=CREDIT_TTL_DAYS),
        note=(
            f"Предоплата {months} мес. Оплачено "
            f"{_fmt_money(invoice.amount)}"
            + (f", начислено {_fmt_money(amount)}"
               if amount != _money(invoice.amount) else "")
            + "."
        ),
        created_at=now,
    )
    db.add(credit)
    previous = _aware(account.prepaid_until)
    if previous is None or period_end > previous:
        account.prepaid_until = period_end
    account.updated_at = now
    await db.flush()
    await notify_user(
        db, master.user_id,
        f"Предоплата зачислена: {_fmt_money(amount)} на баланс.\n"
        f"Сумма будет автоматически закрывать счета до "
        f"{period_end.strftime('%d.%m.%Y')}.",
        audience="system", kind="billing_prepay", link="billing",
    )
    return credit


async def record_payment(
    db: AsyncSession,
    invoice: BillingInvoice,
    *,
    amount: Optional[Decimal] = None,
    method: str = "manual",
    note: Optional[str] = None,
    admin_user_id: Optional[int] = None,
    now: Optional[datetime] = None,
) -> BillingInvoice:
    now = _aware(now) or _now()
    await apply_credits(db, invoice.master_id, now=now)
    due = _due(invoice)
    if due <= 0:
        invoice.status = "paid"
        invoice.paid_at = invoice.paid_at or now
        await _grant_prepayment_credit(db, invoice, now)
        await db.flush()
        return invoice
    value = _money(amount) if amount is not None else due
    if value <= 0:
        return invoice
    value = min(value, due)
    db.add(BillingPayment(
        invoice_id=invoice.id, amount=value, method=method,
        note=note, created_by_user_id=admin_user_id, created_at=now,
    ))
    invoice.paid_amount = _money(invoice.paid_amount) + value
    if _due(invoice) <= 0:
        invoice.status = "paid"
        invoice.paid_at = now
        invoice.payment_method = method
        await _grant_prepayment_credit(db, invoice, now)
    invoice.updated_at = now
    await db.flush()
    await process_master(db, invoice.master_id, now=now)
    return invoice


async def add_manual_credit(
    db: AsyncSession, master_id: int, amount: Decimal,
    note: Optional[str] = None, now: Optional[datetime] = None,
) -> BillingCredit:
    now = _aware(now) or _now()
    value = _money(amount)
    credit = BillingCredit(
        master_id=master_id, source="manual", source_ref=None,
        amount=value, remaining=value,
        expires_at=now + timedelta(days=CREDIT_TTL_DAYS),
        note=note, created_at=now,
    )
    db.add(credit)
    await db.flush()
    await apply_credits(db, master_id, now=now)
    await process_master(db, master_id, now=now)
    return credit


def _fmt_money(value: Any) -> str:
    amount = _money(value)
    if amount == amount.to_integral_value():
        return f"{int(amount)} ₽"
    return f"{amount:.2f} ₽".replace(".", ",")


# ─── Read models ─────────────────────────────────────────────────────

async def serialize_billing(
    db: AsyncSession, master_id: int, now: Optional[datetime] = None,
) -> Optional[dict]:
    now = _aware(now) or _now()
    await process_master(db, master_id, now=now, notify=False)
    master = (await db.execute(
        select(MasterProfile)
        .options(joinedload(MasterProfile.user))
        .where(MasterProfile.id == master_id)
    )).scalar_one_or_none()
    if master is None or not is_billable_master(master):
        return None
    account = await ensure_account(db, master, now=now)
    invoices = (await db.execute(
        select(BillingInvoice).where(
            BillingInvoice.master_id == master_id
        ).order_by(BillingInvoice.period_index.asc())
    )).scalars().all()
    credits = (await db.execute(
        select(BillingCredit).where(
            BillingCredit.master_id == master_id
        ).order_by(BillingCredit.created_at.desc())
    )).scalars().all()
    award = (await db.execute(
        select(ClientBonusAward).where(
            ClientBonusAward.master_id == master_id)
    )).scalar_one_or_none()

    if award is None:
        calc = await compute_client_bonus(db, master_id, account, now=now)
        bonus = {
            "eligible_count": calc["eligible_count"],
            "max_count": CLIENT_BONUS_MAX_CLIENTS,
            "amount": float(calc["amount"]),
            "max_amount": float(CLIENT_BONUS_MAX),
            "status": "pending",
            "total_candidates": calc["total_candidates"],
            "unconfirmed_count": calc["unconfirmed_count"],
            "prompted_count": calc["prompted_count"],
            "unconfirmed_ratio": calc["unconfirmed_ratio"],
            "review_flag": calc["review_flag"],
            "evaluated_at": None,
            "evaluation_at": _iso(
                _aware(account.trial_ends_at) + timedelta(days=7)),
        }
    else:
        bonus = {
            "eligible_count": award.eligible_count,
            "max_count": award.max_count,
            "amount": float(_money(award.amount)),
            "max_amount": float(CLIENT_BONUS_MAX),
            "status": award.status,
            "total_candidates": award.total_candidates,
            "unconfirmed_count": award.unconfirmed_count,
            "prompted_count": (award.details or {}).get("prompted_count", 0),
            "unconfirmed_ratio": (award.details or {}).get(
                "unconfirmed_ratio", 0),
            "review_flag": award.review_flagged,
            "evaluated_at": _iso(award.evaluated_at),
            "evaluation_at": _iso(
                _aware(account.trial_ends_at) + timedelta(days=7)),
        }

    referral_rows = (await db.execute(
        select(MasterReferral, User)
        .join(User, MasterReferral.referred_user_id == User.id)
        .where(MasterReferral.referrer_master_id == master_id)
        .order_by(MasterReferral.created_at.desc())
    )).all()
    referrals_out = []
    for referral, referred_user in referral_rows:
        progress = referral.qualified_count
        if referral.status == "pending" and referral.referred_master_id:
            progress = len(await _referral_qualified_count(
                db, referral.referred_master_id))
        referrals_out.append({
            "id": referral.id,
            "referred_name": referred_user.name or "Коллега",
            "registered_at": _iso(referral.registered_at),
            "status": referral.status,
            "status_label": REFERRAL_LABELS.get(referral.status, referral.status),
            "qualified_count": progress,
            "required_count": REFERRAL_QUALIFY_BOOKINGS,
            "amount": float(_money(referral.amount)),
            "reject_reason": referral.reject_reason,
            "evaluated_at": _iso(referral.evaluated_at),
        })

    referral_credits = [c for c in credits if c.source == "referral_bonus"]
    monthly_invoices = _normal_invoices(invoices)
    total_due = sum((_due(inv) for inv in monthly_invoices), Decimal("0"))
    total_credit = sum((_money(c.remaining) for c in credits), Decimal("0"))
    prepaid_until = _aware(account.prepaid_until)
    prepaid_credit = next(
        (credit for credit in credits
         if credit.source == "prepayment"
         and _money(credit.remaining) > 0
         and (credit.expires_at is None
              or _aware(credit.expires_at) > now)),
        None,
    )
    prepaid_active = bool(
        prepaid_until and prepaid_until > now and prepaid_credit)
    trial_end = _aware(account.trial_ends_at)
    days_left = max(0, (trial_end - now).days)
    if prepaid_active:
        # The prepayment credit pays future monthly invoices automatically;
        # there is nothing to pay manually until it runs out.
        next_at = prepaid_until
        next_amount = Decimal("0")
    elif now < trial_end:
        next_at = trial_end + timedelta(days=1)
        next_amount = Decimal("250")
    else:
        next_index = _next_period_index(monthly_invoices)
        next_at, _, _, next_amount = _invoice_terms(account, next_index)
        # If the next invoice is already generated, point one period ahead.
        if any(inv.period_index == next_index for inv in monthly_invoices):
            next_at, _, _, next_amount = _invoice_terms(
                account, next_index + 1)

    month_quote = _prepayment_quote(
        account, invoices, credits, 1, now)
    year_quote = _prepayment_quote(
        account, invoices, credits, PREPAY_MONTHS, now)
    prepay_reason = month_quote["reason"] or year_quote["reason"]

    return {
        "master_id": master.id,
        "master_name": master.user.name if master.user else "Мастер",
        "access_status": account.access_status,
        "access_status_label": ACCESS_LABELS.get(
            account.access_status, account.access_status),
        "is_blocked": account.access_status in (
            ACCESS_READONLY, ACCESS_PAUSED, ACCESS_SUSPENDED),
        "trial_started_at": _iso(account.trial_started_at),
        "trial_ends_at": _iso(account.trial_ends_at),
        "billing_started_at": _iso(account.billing_started_at),
        "trial_days_left": days_left,
        "review_flag": bool(account.review_flag),
        "bonus_blocked_until": _iso(account.bonus_blocked_until),
        "referral_code": account.referral_code,
        "referral_link": f"/r/{account.referral_code}",
        "next_payment_at": _iso(next_at),
        "next_payment_amount": float(next_amount),
        "prepaid_until": _iso(prepaid_until) if prepaid_active else None,
        "balance": {
            "due": float(_money(total_due)),
            "credit": float(_money(total_credit)),
            "net": float(_money(total_credit - total_due)),
        },
        "prepay": {
            "available": not prepay_reason,
            "reason": prepay_reason,
            "open_invoice_id": month_quote["open_invoice_id"],
            "month": month_quote,
            "year": year_quote,
        },
        "invoices": [{
            "id": inv.id,
            "period_index": inv.period_index,
            "amount": float(_money(inv.amount)),
            "base_amount": (
                float(_money(inv.base_amount))
                if inv.base_amount is not None else None
            ),
            "credits_applied": float(_money(inv.credits_applied)),
            "paid_amount": float(_money(inv.paid_amount)),
            "due_amount": float(_due(inv)),
            "status": inv.status,
            "status_label": INVOICE_LABELS.get(inv.status, inv.status),
            "kind": inv.kind or "monthly",
            "months": inv.months or 1,
            "is_prepay": _is_prepay(inv),
            "issue_at": _iso(inv.issue_at),
            "due_at": _iso(inv.due_at),
            "paid_at": _iso(inv.paid_at),
            "payment_method": inv.payment_method,
            "note": inv.note,
            "period_start": _iso(inv.period_start),
            "period_end": _iso(inv.period_end),
        } for inv in invoices],
        "credits": [{
            "id": c.id,
            "source": c.source,
            "source_label": CREDIT_LABELS.get(c.source, c.source),
            "amount": float(_money(c.amount)),
            "remaining": float(_money(c.remaining)),
            "expires_at": _iso(c.expires_at),
            "note": c.note,
            "created_at": _iso(c.created_at),
        } for c in credits],
        "client_bonus": bonus,
        "referral": {
            "qualified_count": sum(
                1 for r in referral_rows if r[0].status == "qualified"),
            "max_count": REFERRAL_MAX,
            "bonus_total": float(sum(
                (_money(c.amount) for c in referral_credits), Decimal("0"))),
            "max_amount": float(Decimal(REFERRAL_MAX) * REFERRAL_BONUS),
            "click_days": REFERRAL_CLICK_DAYS,
            "credit_days": CREDIT_TTL_DAYS,
        },
        "referrals": referrals_out,
        "payment_instructions": (
            "Оплата подтверждается администратором вручную. "
            "После перевода сообщите администратору сумму и дату платежа — "
            "он отметит счёт оплаченным, и доступ восстановится в тот же день."
        ),
    }


async def billing_overview(
    db: AsyncSession, now: Optional[datetime] = None,
    search: Optional[str] = None, status: Optional[str] = None,
) -> list[dict]:
    now = _aware(now) or _now()
    query = (select(MasterProfile)
             .options(joinedload(MasterProfile.user))
             .order_by(MasterProfile.id.asc()))
    masters = (await db.execute(query)).scalars().all()
    rows = []
    needle = (search or "").strip().lower()
    for master in masters:
        if not is_billable_master(master):
            continue
        if needle:
            haystack = " ".join([
                master.user.name if master.user else "",
                master.user.email if master.user and master.user.email else "",
                str(master.id),
            ]).lower()
            if needle not in haystack:
                continue
        await process_master(db, master.id, now=now, notify=False)
        account = await ensure_account(db, master, now=now)
        if status and status != "all" and account.access_status != status:
            continue
        invoices = (await db.execute(
            select(BillingInvoice).where(
                BillingInvoice.master_id == master.id)
        )).scalars().all()
        credits = (await db.execute(
            select(BillingCredit).where(
                BillingCredit.master_id == master.id)
        )).scalars().all()
        total_due = sum(
            (_due(inv) for inv in _normal_invoices(invoices)), Decimal("0"))
        total_credit = sum((_money(c.remaining) for c in credits), Decimal("0"))
        rows.append({
            "master_id": master.id,
            "master_name": master.user.name if master.user else "Мастер",
            "email": master.user.email if master.user else None,
            "access_status": account.access_status,
            "access_status_label": ACCESS_LABELS.get(
                account.access_status, account.access_status),
            "trial_ends_at": _iso(account.trial_ends_at),
            "balance_due": float(_money(total_due)),
            "balance_credit": float(_money(total_credit)),
            "review_flag": bool(account.review_flag),
            "referral_code": account.referral_code,
        })
    await db.flush()
    return rows


async def get_billing_access(
    db: AsyncSession, master_id: int,
) -> Optional[str]:
    return (await db.execute(
        select(MasterBillingAccount.access_status).where(
            MasterBillingAccount.master_id == master_id)
    )).scalar_one_or_none()


async def is_master_bookable(db: AsyncSession, master_id: int) -> bool:
    row = (await db.execute(
        select(MasterProfile.is_active, MasterProfile.status, User.role)
        .join(User, MasterProfile.user_id == User.id)
        .where(MasterProfile.id == master_id)
    )).one_or_none()
    if (row is None or not row.is_active or row.status != "active"
            or row.role != UserRole.MASTER):
        return False
    status = await get_billing_access(db, master_id)
    return status not in (ACCESS_READONLY, ACCESS_PAUSED, ACCESS_SUSPENDED)


# ─── Delayed visit prompt / confirmation ──────────────────────────────

async def run_visit_prompts_once(session_factory=None) -> int:
    """Bell prompt 48h after the visit; inline «Не был» / «Да, оценю»."""
    factory = session_factory or AsyncSessionLocal
    now = localnow_naive()
    sent = 0
    async with factory() as db:
        rows = (await db.execute(
            select(Appointment, ClientProfile, MasterProfile)
            .join(ClientProfile, Appointment.client_id == ClientProfile.id)
            .join(MasterProfile, Appointment.master_id == MasterProfile.id)
            .outerjoin(Review, Review.appointment_id == Appointment.id)
            .where(
                Appointment.visit_prompt_sent_at.is_(None),
                # Past pending rows are reviewable too: a master must not
                # avoid the quality check by never pressing "complete".
                Appointment.status.notin_(("cancelled", "no_show")),
                # Don't reopen months of history on the first deploy.
                Appointment.appointment_date >= now - timedelta(
                    days=PROMPT_LOOKBACK_DAYS),
                Review.id.is_(None),
            )
            .order_by(Appointment.appointment_date.asc())
            .limit(500)
        )).all()
        for appointment, client, master in rows:
            duration = appointment.duration_minutes or 60
            end = appointment.appointment_date + timedelta(minutes=duration)
            if end + timedelta(hours=48) > now:
                continue
            master_user = (await db.execute(
                select(User).where(User.id == master.user_id)
            )).scalar_one_or_none()
            client_user = (await db.execute(
                select(User).where(User.id == client.user_id)
            )).scalar_one_or_none()
            if master_user is None or client_user is None:
                continue
            appointment.visit_prompt_sent_at = datetime.now(timezone.utc)
            appointment.visit_confirmation_status = "pending"
            await notify_user(
                db, client_user.id,
                f"Как прошёл визит к мастеру {master_user.name or ''}?\n"
                "Поставьте оценку и оставьте отзыв. Если вас не было — "
                "нажмите «Не был».",
                audience="system", kind="visit_feedback",
                appointment_id=appointment.id,
                link=f"review:{appointment.id}",
            )
            sent += 1
        await db.commit()
    if sent:
        logger.info("Visit prompts sent: %s", sent)
    return sent


async def confirm_visit(
    db: AsyncSession, user: User, appointment_id: int, status: str,
    now: Optional[datetime] = None,
) -> dict:
    """Client answered the delayed prompt: confirmed visit or «Не был»."""
    now = _aware(now) or _now()
    if status not in ("confirmed", "disputed"):
        raise ValueError("invalid status")
    row = (await db.execute(
        select(Appointment)
        .join(ClientProfile, Appointment.client_id == ClientProfile.id)
        .where(
            Appointment.id == appointment_id,
            ClientProfile.user_id == user.id,
        )
    )).scalar_one_or_none()
    if row is None:
        raise LookupError("appointment not found")
    if row.status in ("cancelled", "no_show"):
        raise ValueError("visit cancelled")

    row.visit_confirmation_status = status
    row.visit_confirmation_at = now
    await db.execute(
        update(Notification)
        .where(
            Notification.recipient_id == user.id,
            Notification.appointment_id == appointment_id,
            Notification.kind == "visit_feedback",
        )
        .values(is_read=True, read_at=now, resolved_at=now)
    )
    if status == "disputed":
        master = (await db.execute(
            select(MasterProfile).where(MasterProfile.id == row.master_id)
        )).scalar_one_or_none()
        if master is not None:
            await notify_user(
                db, master.user_id,
                "Клиент отметил, что визита не было. Запись помечена как "
                "спорная — проверьте её в расписании.",
                sender_id=user.id, audience="system",
                kind="visit_dispute", appointment_id=row.id,
                link=f"appointments:{row.id}",
            )
    await db.flush()
    return {
        "ok": True,
        "appointment_id": row.id,
        "status": status,
        "review_url": f"/cabinet?review={row.id}" if status == "confirmed" else None,
    }


# ─── Background loops ─────────────────────────────────────────────────

async def run_billing_tick_once(session_factory=None) -> int:
    factory = session_factory or AsyncSessionLocal
    processed = 0
    async with factory() as db:
        ids = (await db.execute(
            select(MasterProfile.id)
            .join(User, MasterProfile.user_id == User.id)
            .where(User.role == UserRole.MASTER)
            .order_by(MasterProfile.id.asc())
        )).scalars().all()
        for master_id in ids:
            try:
                await process_master(db, master_id)
                await db.commit()
                processed += 1
            except Exception:  # noqa: BLE001 - one bad row must not stop the loop
                await db.rollback()
                logger.exception("Billing tick failed for master %s", master_id)
    await run_visit_prompts_once(session_factory=factory)
    return processed


async def billing_loop(interval_seconds: int = 15 * 60) -> None:
    while True:
        try:
            await run_billing_tick_once()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001
            logger.exception("Billing loop iteration failed")
        await asyncio.sleep(interval_seconds)

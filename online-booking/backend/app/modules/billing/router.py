"""Billing APIs: master summary, superadmin overview and manual ledger actions."""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies.auth import require_master, require_super_admin
from app.models.billing import BillingInvoice
from app.models.master_profile import MasterProfile
from app.models.user import User, UserRole
from app.services.audit import log_action
from app.services.billing import (
    ACCESS_LABELS,
    BillingValidationError,
    PREPAY_KIND_HALF_YEAR,
    PREPAY_KIND_MONTH,
    PREPAY_KIND_YEAR,
    add_manual_credit,
    billing_overview,
    create_prepayment,
    record_payment,
    serialize_billing,
)
from app.services.notifications import notify_user

router = APIRouter(prefix="/billing", tags=["billing"])


class PaymentRequest(BaseModel):
    amount: Optional[Decimal] = Field(default=None, ge=0)
    method: str = Field(default="manual", max_length=40)
    note: Optional[str] = Field(default=None, max_length=1000)


class PrepayRequest(BaseModel):
    months: int = Field(ge=1, le=12)


class CreditRequest(BaseModel):
    amount: Decimal = Field(gt=0, le=100000)
    note: Optional[str] = Field(default=None, max_length=1000)


class ReviewActionRequest(BaseModel):
    action: str = Field(pattern="^(clear|block)$")
    note: Optional[str] = Field(default=None, max_length=1000)


@router.get("/me")
async def my_billing(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Current master's trial, invoices, credits, client bonus and referrals."""
    if master.role != UserRole.MASTER or master.master_profile is None:
        raise HTTPException(status_code=400, detail="Доступно только мастеру")
    result = await serialize_billing(db, master.master_profile.id)
    if result is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    # serialize_billing is not a pure read: it can materialize invoices,
    # evaluate day-21 bonuses and send bells. Persist those side effects.
    await db.commit()
    return result


@router.get("/overview")
async def overview(
    search: Optional[str] = Query(default=None, max_length=200),
    status: Optional[str] = Query(default="all", max_length=20),
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    rows = await billing_overview(db, search=search, status=status)
    await db.commit()
    return {
        "items": rows,
        "status_labels": ACCESS_LABELS,
        "total": len(rows),
        "summary": {
            "due": round(sum(r["balance_due"] for r in rows), 2),
            "credit": round(sum(r["balance_credit"] for r in rows), 2),
            "readonly": sum(1 for r in rows
                            if r["access_status"] == "readonly"),
            "paused": sum(1 for r in rows
                          if r["access_status"] == "paused"),
            "review": sum(1 for r in rows if r["review_flag"]),
        },
    }


@router.get("/masters/{master_id}")
async def master_billing(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await serialize_billing(db, master_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    await db.commit()
    return result


@router.post("/prepay")
async def prepay(
    data: PrepayRequest,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Create an optional 1-, 6- or 12-month prepayment invoice for the master."""
    if master.role != UserRole.MASTER or master.master_profile is None:
        raise HTTPException(status_code=400, detail="Доступно только мастеру")
    try:
        invoice, quote = await create_prepayment(
            db, master.master_profile.id, data.months)
    except BillingValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except IntegrityError as exc:
        # Two tabs / double-clicks can race on the negative period index.
        await db.rollback()
        raise HTTPException(
            status_code=409, detail="Счёт на предоплату уже создан") from exc
    await log_action(
        db, master.id, "billing.prepay_request", "invoice", invoice.id,
        json.dumps({"months": data.months, "amount": str(invoice.amount)},
                   ensure_ascii=False),
    )
    await db.commit()
    billing = await serialize_billing(db, master.master_profile.id)
    await db.commit()
    return {
        "ok": True,
        "invoice_id": invoice.id,
        "prepay": quote,
        "billing": billing,
    }


@router.post("/prepay/cancel")
async def cancel_prepayment(
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Cancel the master's own unpaid prepayment request, if any."""
    if master.role != UserRole.MASTER or master.master_profile is None:
        raise HTTPException(status_code=400, detail="Доступно только мастеру")
    invoice = (await db.execute(
        select(BillingInvoice)
        .where(
            BillingInvoice.master_id == master.master_profile.id,
            BillingInvoice.status == "open",
            BillingInvoice.kind.in_((PREPAY_KIND_MONTH, PREPAY_KIND_HALF_YEAR,
                                      PREPAY_KIND_YEAR)),
        )
        .order_by(BillingInvoice.id.desc())
    )).scalars().first()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Заявка на предоплату не найдена")
    if Decimal(invoice.paid_amount or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="По счёту уже есть оплата — отмена недоступна, свяжитесь с поддержкой",
        )

    now = datetime.now(timezone.utc)
    invoice.status = "void"
    invoice.updated_at = now
    invoice.note = ((invoice.note or "") + "\nСчёт отменён мастером.").strip()
    await log_action(
        db, master.id, "billing.prepay_cancel", "invoice", invoice.id,
    )
    admin_ids = (await db.execute(
        select(User.id).where(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True),
        )
    )).scalars().all()
    for admin_id in admin_ids:
        await notify_user(
            db, admin_id,
            f"Мастер {master.name or 'без имени'} отменил заявку на предоплату "
            f"({invoice.months or 1} мес.).",
            audience="support", kind="billing_prepay", link="billing",
        )
    await db.commit()
    billing = await serialize_billing(db, master.master_profile.id)
    await db.commit()
    return {"ok": True, "billing": billing}


@router.post("/invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: int,
    data: PaymentRequest,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    invoice = (await db.execute(
        select(BillingInvoice).where(BillingInvoice.id == invoice_id)
    )).scalar_one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Счёт не найден")
    if invoice.status == "paid":
        raise HTTPException(status_code=400, detail="Счёт уже оплачен")
    if invoice.status == "void":
        raise HTTPException(status_code=400, detail="Счёт отменён")
    await record_payment(
        db, invoice, amount=data.amount, method=data.method,
        note=data.note, admin_user_id=super_admin.id,
    )
    await log_action(
        db, super_admin.id, "billing.payment", "invoice", invoice.id,
        json.dumps({"amount": str(data.amount), "method": data.method},
                   ensure_ascii=False),
    )
    await db.commit()
    result = await serialize_billing(db, invoice.master_id)
    await db.commit()
    return {"ok": True, "invoice_id": invoice.id, "billing": result}


@router.post("/masters/{master_id}/credits")
async def create_credit(
    master_id: int,
    data: CreditRequest,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    master = (await db.execute(
        select(MasterProfile)
        .join(User, MasterProfile.user_id == User.id)
        .where(
            MasterProfile.id == master_id,
            User.role == UserRole.MASTER,
        )
    )).scalar_one_or_none()
    if master is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    credit = await add_manual_credit(
        db, master_id, data.amount, note=data.note)
    await log_action(
        db, super_admin.id, "billing.credit", "master", master_id,
        json.dumps({"amount": str(data.amount), "note": data.note},
                   ensure_ascii=False),
    )
    await db.commit()
    billing = await serialize_billing(db, master_id)
    await db.commit()
    return {
        "ok": True,
        "credit_id": credit.id,
        "billing": billing,
    }


@router.post("/masters/{master_id}/review")
async def review_action(
    master_id: int,
    data: ReviewActionRequest,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    from datetime import datetime, timezone
    from app.models.billing import MasterBillingAccount

    account = (await db.execute(
        select(MasterBillingAccount).where(
            MasterBillingAccount.master_id == master_id)
    )).scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=404, detail="Биллинг мастера не найден")
    if data.action == "clear":
        account.review_flag = False
        account.bonus_blocked_until = None
    else:
        account.review_flag = True
        account.bonus_blocked_until = (
            datetime.now(timezone.utc).replace(microsecond=0)
            + timedelta(days=90)
        )
    account.updated_at = datetime.now(timezone.utc)
    await log_action(
        db, super_admin.id, f"billing.review.{data.action}",
        "master", master_id,
        json.dumps({"note": data.note}, ensure_ascii=False),
    )
    await db.commit()
    billing = await serialize_billing(db, master_id)
    await db.commit()
    return {"ok": True, "billing": billing}


@router.post("/masters/{master_id}/tick")
async def tick_master(
    master_id: int,
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db),
):
    from app.services.billing import process_master

    result = await process_master(db, master_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Мастер не найден")
    await db.commit()
    billing = await serialize_billing(db, master_id)
    await db.commit()
    return {"ok": True, "result": result, "billing": billing}

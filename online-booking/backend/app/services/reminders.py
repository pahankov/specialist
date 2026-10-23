"""Appointment reminders and the master's morning digest."""
import asyncio
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.logging_config import get_logger
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.master_profile import MasterProfile
from app.models.notification_preference import NotificationPreference
from app.models.service import Service
from app.models.user import User, UserRole
from app.models.working_hour import WorkingHour
from app.services.booking import format_slot
from app.services.notification_settings import get_or_create_preference
from app.services.notifications import notify_user
from app.utils import localnow_naive, utcnow

logger = get_logger(__name__)

REMINDER_INTERVAL_SECONDS = 5 * 60
DIGEST_INTERVAL_SECONDS = 60
DAY_SOON = timedelta(hours=24)
DAY_SOON_2H = timedelta(hours=2)


def _label(appointment: Appointment, service_name: str | None) -> str:
    return appointment.bundle_name or service_name or "запись"


def _address(master: MasterProfile) -> str:
    value = (master.cabinet_address or "").strip()
    return f", {value}" if value else ""


def _text(appointment: Appointment, master: User,
          master_profile: MasterProfile, service_name: str | None) -> str:
    return (
        f"Напоминаем о записи: {format_slot(appointment.appointment_date)} — "
        f"{_label(appointment, service_name)} у {master.name or 'мастера'}"
        f"{_address(master_profile)}. Если планы изменились, отмените запись "
        f"в кабинете."
    )


async def _claim(db: AsyncSession, appointment_id: int, field: str) -> bool:
    column = getattr(Appointment, field)
    result = await db.execute(
        update(Appointment)
        .where(Appointment.id == appointment_id, column.is_(None))
        .values({field: utcnow()})
    )
    return bool(result.rowcount)


async def run_appointment_reminders_once(session_factory=None) -> int:
    factory = session_factory or AsyncSessionLocal
    now = localnow_naive()
    sent = 0
    async with factory() as db:
        rows = (await db.execute(
            select(Appointment, MasterProfile, User, Service, ClientProfile)
            .join(MasterProfile, Appointment.master_id == MasterProfile.id)
            .join(User, MasterProfile.user_id == User.id)
            .join(ClientProfile, Appointment.client_id == ClientProfile.id)
            .outerjoin(Service, Appointment.service_id == Service.id)
            .where(
                Appointment.status.in_(("pending", "confirmed")),
                Appointment.appointment_date > now,
                or_(
                    Appointment.reminder_24h_sent_at.is_(None),
                    Appointment.reminder_2h_sent_at.is_(None),
                ),
            )
            .order_by(Appointment.appointment_date.asc())
            .limit(500)
        )).all()
        for appointment, master_profile, master, service, client in rows:
            appointment_at = appointment.appointment_date.replace(tzinfo=None)
            due_24h = appointment_at - DAY_SOON
            due_2h = appointment_at - DAY_SOON_2H
            if appointment.reminder_24h_sent_at is None and now >= due_24h:
                if not await _claim(db, appointment.id, "reminder_24h_sent_at"):
                    continue
                if now < due_2h:
                    pref = await get_or_create_preference(db, client.user_id)
                    if pref.reminders_enabled:
                        await notify_user(
                            db, client.user_id,
                            _text(appointment, master, master_profile,
                                  service.name if service else None),
                            audience="booking", kind="appointment_reminder_24h",
                            appointment_id=appointment.id,
                            link=f"appointments:{appointment.id}",
                        )
                        sent += 1
            if appointment.reminder_2h_sent_at is None and now >= due_2h:
                if not await _claim(db, appointment.id, "reminder_2h_sent_at"):
                    continue
                pref = await get_or_create_preference(db, client.user_id)
                if pref.reminders_enabled:
                    await notify_user(
                        db, client.user_id,
                        _text(appointment, master, master_profile,
                              service.name if service else None),
                        audience="booking", kind="appointment_reminder_2h",
                        appointment_id=appointment.id,
                        link=f"appointments:{appointment.id}",
                    )
                    sent += 1
        await db.commit()
    if sent:
        logger.info("Appointment reminders sent: %s", sent)
    return sent


def _digest_text(rows, day: str) -> str:
    if not rows:
        return (f"Доброе утро! Сегодня, {day}, записей нет — "
                f"свободный день.")
    lines = [
        f"Доброе утро! Сегодня, {day}, у вас {len(rows)} "
        f"{'запись' if len(rows) == 1 else ('записи' if len(rows) < 5 else 'записей')}."
    ]
    total = Decimal("0")
    for appointment, client_name, service_name, price in rows:
        item = _label(appointment, service_name)
        status = "подтверждена" if appointment.status == "confirmed" else "ожидает"
        lines.append(
            f"• {appointment.appointment_date.strftime('%H:%M')} — "
            f"{client_name or 'клиент'}: {item} ({status})"
        )
        total += Decimal(str(price or 0))
    if total:
        lines.append(f"\nОжидаемая выручка: {total:.0f} ₽.")
    return "\n".join(lines)


async def run_master_digest_once(session_factory=None) -> int:
    factory = session_factory or AsyncSessionLocal
    now = localnow_naive()
    today = now.date()
    day_start = datetime.combine(today, time.min)
    day_end = day_start + timedelta(days=1)
    sent = 0
    async with factory() as db:
        masters = (await db.execute(
            select(MasterProfile, User)
            .join(User, MasterProfile.user_id == User.id)
            .where(
                User.role == UserRole.MASTER,
                User.is_active == True,  # noqa: E712
                MasterProfile.is_active == True,  # noqa: E712
                MasterProfile.status != "suspended",
            )
        )).all()
        for master_profile, master in masters:
            pref = await get_or_create_preference(db, master.id)
            if not pref.master_digest_enabled:
                continue
            if pref.last_digest_on == today:
                continue
            work = (await db.execute(
                select(WorkingHour)
                .where(
                    WorkingHour.master_id == master_profile.id,
                    WorkingHour.schedule_date == today,
                    WorkingHour.is_active == True,  # noqa: E712
                )
                .order_by(WorkingHour.start_time.asc())
                .limit(1)
            )).scalar_one_or_none()
            start_time = (work.start_time if work is not None else time(
                hour=master_profile.work_start_hour or 8,
            ))
            start_at = datetime.combine(today, start_time)
            digest_at = start_at - timedelta(
                minutes=int(pref.digest_lead_minutes or 60))
            if now < digest_at or now >= start_at:
                continue
            claimed = await db.execute(
                update(NotificationPreference)
                .where(
                    NotificationPreference.id == pref.id,
                    or_(
                        NotificationPreference.last_digest_on.is_(None),
                        NotificationPreference.last_digest_on != today,
                    ),
                )
                .values(last_digest_on=today)
            )
            if not claimed.rowcount:
                continue
            rows = (await db.execute(
                select(
                    Appointment,
                    User.name,
                    Service.name,
                    func.coalesce(Appointment.price, Service.price),
                )
                .join(ClientProfile, Appointment.client_id == ClientProfile.id)
                .join(User, ClientProfile.user_id == User.id)
                .outerjoin(Service, Appointment.service_id == Service.id)
                .where(
                    Appointment.master_id == master_profile.id,
                    Appointment.appointment_date >= day_start,
                    Appointment.appointment_date < day_end,
                    Appointment.status.in_(("pending", "confirmed")),
                )
                .order_by(Appointment.appointment_date.asc())
            )).all()
            await notify_user(
                db, master.id,
                _digest_text(rows, now.strftime("%d.%m")),
                audience="system", kind="master_digest",
                link="appointments",
            )
            sent += 1
            await db.commit()
    if sent:
        logger.info("Master digests sent: %s", sent)
    return sent


async def reminders_loop() -> None:
    while True:
        try:
            await run_appointment_reminders_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Appointment reminders sweep failed: %s", exc)
        await asyncio.sleep(REMINDER_INTERVAL_SECONDS)


async def master_digest_loop() -> None:
    while True:
        try:
            await run_master_digest_once()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Master digest sweep failed: %s", exc)
        await asyncio.sleep(DIGEST_INTERVAL_SECONDS)

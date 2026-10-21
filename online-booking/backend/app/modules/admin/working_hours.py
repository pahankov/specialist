"""Admin working hours CRUD endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import date, datetime, time, timedelta

from app.database import get_db
from app.models.appointment import Appointment
from app.models.working_hour import WorkingHour
from app.models.user import User, UserRole
from app.models.master_profile import MasterProfile
from app.schemas.working_hour import WorkingHourCreate, WorkingHourUpdate, WorkingHourResponse
from app.dependencies.auth import require_master
from app.dependencies.crud import get_owned_or_404, get_or_404
from app.services.audit import log_action
from app.services.master_status import update_master_status_from_working_hours
from app.modules.admin.helpers import get_master_profile_id
from app.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()


@router.get("/working-hours", response_model=List[WorkingHourResponse])
async def get_working_hours(
    master: User = Depends(require_master),
    master_id: Optional[int] = Query(None, description="Filter by master ID (superadmin only)"),
    db: AsyncSession = Depends(get_db)
):
    """Get working hours for the authenticated master (or specified master for superadmin)."""
    logger.info("Get working hours: master=%s, master_id=%s", master.id, master_id)
    is_admin = master.role == "ADMIN"
    
    if is_admin and master_id is not None:
        query = select(WorkingHour).where(WorkingHour.master_id == master_id).order_by(WorkingHour.schedule_date)
    else:
        mp_id = await get_master_profile_id(db, master)
        query = select(WorkingHour).where(WorkingHour.master_id == mp_id).order_by(WorkingHour.schedule_date)
    
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/working-hours", response_model=WorkingHourResponse, status_code=201)
async def create_working_hour(
    data: WorkingHourCreate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Create working hours.

    Regular master: always for themselves. Superadmin: MUST pass
    data.master_id (target MasterProfile.id) — superadmins have no
    profile of their own, "adding to self" is rejected with 400.
    """
    if master.role == UserRole.ADMIN:
        if data.master_id is None:
            raise HTTPException(
                status_code=400,
                detail="Укажите мастера (master_id): суперпользователь не может добавить часы себе",
            )
        target = await db.execute(
            select(MasterProfile).where(MasterProfile.id == data.master_id)
        )
        if target.scalar_one_or_none() is None:
            raise HTTPException(status_code=404, detail="Мастер не найден")
        mp_id = data.master_id
    else:
        mp_id = await get_master_profile_id(db, master)
    dup = (await db.execute(
        select(WorkingHour.id).where(
            WorkingHour.master_id == mp_id,
            WorkingHour.schedule_date == data.schedule_date)
    )).scalar_one_or_none()
    if dup is not None:
        raise HTTPException(
            status_code=409,
            detail="На этот день часы уже заданы — отредактируйте их")
    hour = WorkingHour(
        master_id=mp_id, schedule_date=data.schedule_date,
        start_time=data.start_time,
        end_time=data.end_time
    )
    db.add(hour)
    await db.flush()
    await db.refresh(hour)
    await log_action(db, master.id, "create", "working_hour", hour.id, f"{data.schedule_date}: {data.start_time}-{data.end_time}", level="info")
    await db.commit()
    
    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()
    
    return hour


class ScheduleApplyRequest(BaseModel):
    """Bulk-apply a repeating work/rest cycle to a date range.

    The cycle starts at ``cycle_anchor`` (day 0 is a work day):
    ``work_days`` work days followed by ``off_days`` rest days. This covers
    5/2, 2/2, 1/3, 7/0 and arbitrary N/M patterns.
    """

    master_id: Optional[int] = None  # MasterProfile.id, superadmin only
    range_start: date
    range_end: date
    cycle_work_days: int = Field(ge=1, le=31)
    cycle_off_days: int = Field(ge=0, le=31)
    cycle_anchor: date
    start_time: time
    end_time: time
    replace_off_days: bool = True


class ScheduleApplyResponse(BaseModel):
    master_id: int
    range_start: date
    range_end: date
    effective_start: Optional[date] = None
    work_days: int
    off_days: int
    created: int
    updated: int
    removed: int
    skipped_booked: int
    skipped_dates: List[str]
    window_start_hour: int
    window_end_hour: int


@router.post("/working-hours/apply", response_model=ScheduleApplyResponse)
async def apply_schedule_cycle(
    data: ScheduleApplyRequest,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Apply a work/rest cycle with the same hours to a whole month/range.

    Safety rules:
    - Past days are never touched (the effective range starts today).
    - A day holding a live appointment is left as-is; shrinking or removing
      its working hours would strand the booking.
    - The whole operation is one transaction; the audit log gets one entry.

    The work window is reset to the template's hours, so the schedule shows
    exactly the chosen granules. Days that keep older hours (past days or
    days with live bookings) still render their own saved range in the UI.
    """
    if data.range_start > data.range_end:
        raise HTTPException(status_code=400, detail="Начало периода позже конца")
    if (data.range_end - data.range_start).days > 366:
        raise HTTPException(status_code=400, detail="Период не может быть длиннее года")
    if data.start_time >= data.end_time:
        raise HTTPException(status_code=400, detail="Начало рабочего дня должно быть раньше конца")

    profile = await _resolve_window_profile(db, master, data.master_id)
    today = date.today()
    effective_start = max(data.range_start, today)
    effective_end = data.range_end

    if effective_start > effective_end:
        return ScheduleApplyResponse(
            master_id=profile.id,
            range_start=data.range_start,
            range_end=data.range_end,
            effective_start=None,
            work_days=0,
            off_days=0,
            created=0,
            updated=0,
            removed=0,
            skipped_booked=0,
            skipped_dates=[],
            window_start_hour=profile.work_start_hour if profile.work_start_hour is not None else 8,
            window_end_hour=profile.work_end_hour if profile.work_end_hour is not None else 22,
        )

    cycle_len = data.cycle_work_days + data.cycle_off_days
    rows = (await db.execute(
        select(WorkingHour).where(
            WorkingHour.master_id == profile.id,
            WorkingHour.schedule_date >= effective_start,
            WorkingHour.schedule_date <= effective_end,
        )
    )).scalars().all()
    rows_by_date = {row.schedule_date: row for row in rows}

    # Live bookings are derived from the same date range. Cancelled history
    # does not protect a day: it is not a resource conflict.
    busy_datetimes = (await db.execute(
        select(Appointment.appointment_date).where(
            Appointment.master_id == profile.id,
            Appointment.appointment_date >= datetime.combine(effective_start, time.min),
            Appointment.appointment_date < datetime.combine(effective_end + timedelta(days=1), time.min),
            Appointment.status != "cancelled",
        )
    )).scalars().all()
    busy_days = {dt.date() for dt in busy_datetimes if dt is not None}

    created = updated = removed = skipped_booked = 0
    work_days = off_days = 0
    skipped_dates: List[str] = []

    day = effective_start
    while day <= effective_end:
        phase = (day - data.cycle_anchor).days % cycle_len
        is_work = phase < data.cycle_work_days
        row = rows_by_date.get(day)

        if is_work:
            work_days += 1
            needs_change = (
                row is None
                or row.start_time != data.start_time
                or row.end_time != data.end_time
                or not row.is_active
            )
            if needs_change and day in busy_days:
                skipped_booked += 1
                skipped_dates.append(day.isoformat())
            elif row is None:
                row = WorkingHour(
                    master_id=profile.id,
                    schedule_date=day,
                    start_time=data.start_time,
                    end_time=data.end_time,
                    is_active=True,
                )
                db.add(row)
                rows_by_date[day] = row
                created += 1
            elif needs_change:
                row.start_time = data.start_time
                row.end_time = data.end_time
                row.is_active = True
                updated += 1
        else:
            off_days += 1
            if data.replace_off_days and row is not None:
                if day in busy_days:
                    skipped_booked += 1
                    skipped_dates.append(day.isoformat())
                else:
                    await db.delete(row)
                    del rows_by_date[day]
                    removed += 1
        day += timedelta(days=1)

    # Reset the displayed window to the applied template: the master asked
    # for exactly these granules. Older preserved days (past/booked) are
    # rendered by the frontend from their own stored range.
    start_hour = data.start_time.hour
    end_hour = data.end_time.hour + (1 if (data.end_time.minute or data.end_time.second) else 0)
    profile.work_start_hour = start_hour
    profile.work_end_hour = end_hour

    await log_action(
        db, master.id, "apply", "working_hour", profile.id,
        f"{effective_start}..{effective_end}: цикл {data.cycle_work_days}/{data.cycle_off_days}, "
        f"{data.start_time.strftime('%H:%M')}-{data.end_time.strftime('%H:%M')}; "
        f"создано {created}, обновлено {updated}, удалено {removed}",
        level="info",
    )
    await db.flush()
    await update_master_status_from_working_hours(db, profile)
    await db.commit()

    return ScheduleApplyResponse(
        master_id=profile.id,
        range_start=data.range_start,
        range_end=data.range_end,
        effective_start=effective_start,
        work_days=work_days,
        off_days=off_days,
        created=created,
        updated=updated,
        removed=removed,
        skipped_booked=skipped_booked,
        skipped_dates=skipped_dates,
        window_start_hour=profile.work_start_hour,
        window_end_hour=profile.work_end_hour,
    )


@router.patch("/working-hours/{hour_id}", response_model=WorkingHourResponse)
async def update_working_hour(
    hour_id: int,
    data: WorkingHourUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Update working hours (superadmin: any hour; master: own only)."""
    if master.role == UserRole.ADMIN:
        hour = await get_or_404(db, WorkingHour, hour_id)
    else:
        mp_id = await get_master_profile_id(db, master)
        hour = await get_owned_or_404(db, WorkingHour, hour_id, mp_id)
    changes = []
    if data.schedule_date is not None:
        hour.schedule_date = data.schedule_date
        changes.append(f"дата: {data.schedule_date}")
    if data.start_time is not None:
        hour.start_time = data.start_time
        changes.append(f"начало: {data.start_time}")
    if data.end_time is not None:
        hour.end_time = data.end_time
        changes.append(f"конец: {data.end_time}")
    if data.is_active is not None:
        hour.is_active = data.is_active
        changes.append(f"активность: {data.is_active}")
    await log_action(db, master.id, "update", "working_hour", hour_id, ", ".join(changes) if changes else "Обновление", level="info")
    await db.commit()
    await db.refresh(hour)
    
    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()
    
    return hour


@router.delete("/working-hours/{hour_id}", status_code=204)
async def delete_working_hour(
    hour_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Delete working hours (superadmin: any hour; master: own only)."""
    if master.role == UserRole.ADMIN:
        hour = await get_or_404(db, WorkingHour, hour_id)
    else:
        mp_id = await get_master_profile_id(db, master)
        hour = await get_owned_or_404(db, WorkingHour, hour_id, mp_id)
    await log_action(db, master.id, "delete", "working_hour", hour_id, f"{hour.schedule_date}: {hour.start_time}-{hour.end_time}", level="warning")
    await db.delete(hour)
    await db.commit()
    
    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()
    
    return None


@router.post("/working-hours/{hour_id}/toggle-active", response_model=WorkingHourResponse)
async def toggle_working_hour_active(
    hour_id: int,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db)
):
    """Toggle working hour active/inactive status (superadmin: any hour)."""
    if master.role == UserRole.ADMIN:
        hour = await get_or_404(db, WorkingHour, hour_id)
    else:
        mp_id = await get_master_profile_id(db, master)
        hour = await get_owned_or_404(db, WorkingHour, hour_id, mp_id)
    hour.is_active = not hour.is_active
    await db.commit()
    await db.refresh(hour)

    # Auto-update master status based on working hours
    mp = await db.execute(select(MasterProfile).where(MasterProfile.id == hour.master_id))
    mp_profile = mp.scalar_one_or_none()
    if mp_profile:
        await update_master_status_from_working_hours(db, mp_profile)
    await db.commit()

    return hour


class WorkWindowResponse(BaseModel):
    master_id: int
    start_hour: int
    end_hour: int


class WorkWindowUpdate(BaseModel):
    master_id: Optional[int] = None  # MasterProfile.id, superadmin only
    start_hour: int
    end_hour: int


async def _resolve_window_profile(
    db: AsyncSession, master: User, master_id: Optional[int]
) -> MasterProfile:
    """Target profile for work-window reads/writes.

    master_id is a MasterProfile.id (same convention as /working-hours).
    """
    if master.role == UserRole.ADMIN:
        if master_id is None:
            raise HTTPException(
                status_code=400,
                detail="Укажите мастера (master_id): у суперпользователя нет своего расписания",
            )
        result = await db.execute(select(MasterProfile).where(MasterProfile.id == master_id))
        profile = result.scalar_one_or_none()
        if profile is None:
            raise HTTPException(status_code=404, detail="Мастер не найден")
        return profile
    mp_id = await get_master_profile_id(db, master)
    result = await db.execute(select(MasterProfile).where(MasterProfile.id == mp_id))
    profile = result.scalar_one_or_none()
    if profile is None:
        raise HTTPException(status_code=404, detail="Профиль мастера не найден")
    return profile


@router.get("/work-window", response_model=WorkWindowResponse)
async def get_work_window(
    master: User = Depends(require_master),
    master_id: Optional[int] = Query(None, description="MasterProfile.id (superadmin only)"),
    db: AsyncSession = Depends(get_db),
):
    """Daily work window that drives schedule granules (whole hours)."""
    profile = await _resolve_window_profile(db, master, master_id)
    return WorkWindowResponse(
        master_id=profile.id,
        start_hour=profile.work_start_hour if profile.work_start_hour is not None else 8,
        end_hour=profile.work_end_hour if profile.work_end_hour is not None else 22,
    )


@router.patch("/work-window", response_model=WorkWindowResponse)
async def update_work_window(
    data: WorkWindowUpdate,
    master: User = Depends(require_master),
    db: AsyncSession = Depends(get_db),
):
    """Set daily work window, e.g. 3-23 renders granules 03:00-23:00."""
    if not (0 <= data.start_hour <= 23 and 1 <= data.end_hour <= 24):
        raise HTTPException(status_code=400, detail="Часы должны быть в диапазоне 0-24")
    if data.start_hour >= data.end_hour:
        raise HTTPException(status_code=400, detail="Начало должно быть раньше конца")
    profile = await _resolve_window_profile(db, master, data.master_id)
    profile.work_start_hour = data.start_hour
    profile.work_end_hour = data.end_hour
    await log_action(
        db, master.id, "update", "work_window", profile.id,
        f"Рабочее время {data.start_hour}:00-{data.end_hour}:00", level="info",
    )
    await db.commit()
    await db.refresh(profile)
    return WorkWindowResponse(
        master_id=profile.id, start_hour=profile.work_start_hour, end_hour=profile.work_end_hour
    )

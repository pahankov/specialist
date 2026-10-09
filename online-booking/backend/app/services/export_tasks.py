"""Background export tasks for CSV generation.

These functions stay SYNC on purpose: RQ workers execute them in a sync
context (``bg_task_service.enqueue``). The inner ``_generate`` coroutine is
driven via :func:`_run` which uses ``asyncio.run`` when there is no running
loop and a dedicated thread otherwise (calling ``asyncio.run`` inside a
running loop raises ``RuntimeError`` and would block the server loop).
"""
import asyncio
import concurrent.futures
import csv
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def _run(coro):
    """Drive a coroutine from sync code without breaking a running loop."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result()


def export_appointments_csv_task(
    status: Optional[str] = None,
    include_master: bool = False,
) -> dict:
    """
    Generate appointments CSV in background.
    Returns file content and metadata.
    """
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload, aliased
    from app.database import AsyncSessionLocal
    from app.models.appointment import Appointment
    from app.models.client_profile import ClientProfile
    from app.models.user import User
    from app.models.service import Service
    from app.models.master_profile import MasterProfile

    ClientUser = aliased(User)
    MasterUser = aliased(User)

    async def _generate():
        logger.info("Export appointments CSV: status=%r include_master=%s", status, include_master)
        async with AsyncSessionLocal() as db:
            query = (
                select(Appointment, ClientUser.name.label("client_name"), ClientUser.phone.label("client_phone"),
                       Service.name.label("service_name"), Service.price.label("service_price"),
                       MasterUser.name.label("master_name"))
                .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
                .join(ClientUser, ClientProfile.user_id == ClientUser.id, isouter=True)
                .join(Service, Appointment.service_id == Service.id, isouter=True)
                .join(MasterProfile, Appointment.master_id == MasterProfile.id, isouter=True)
                .join(MasterUser, MasterProfile.user_id == MasterUser.id, isouter=True)
                .order_by(Appointment.appointment_date.desc())
            )

            if status:
                query = query.where(Appointment.status == status)

            result = await db.execute(query)
            rows = result.all()
            logger.info("Fetched %d appointment rows for CSV export", len(rows))

            output = io.StringIO()
            output.write("ID,Дата,Клиент,Телефон,Услуга,Цена,Статус,Примечания")
            if include_master:
                output.write(",Мастер")
            output.write("\n")

            for i, row in enumerate(rows):
                a = row[0]
                line = (
                    f"{a.id},{a.appointment_date.strftime('%Y-%m-%d %H:%M') if a.appointment_date else ''},"
                    f"{row[1] or ''},{row[2] or ''},{row[3] or ''},"
                    f"{float(row[4]) if row[4] else 0},{a.status},{a.notes or ''}"
                )
                if include_master:
                    line += f",{row[5] or ''}"
                output.write(line + "\n")
                if (i + 1) % 100 == 0:
                    logger.debug("CSV rows written: %d", i + 1)

            logger.info("CSV export complete: %d rows, filename=%s", len(rows),
                        f"appointments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
            return {
                "filename": f"appointments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "content": output.getvalue(),
                "rows": len(rows),
                "media_type": "text/csv; charset=utf-8",
            }

    return _run(_generate())


def export_clients_csv_task() -> dict:
    """Generate clients CSV in background."""
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User
    from app.models.client_profile import ClientProfile

    async def _generate():
        logger.info("Export clients CSV")
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User, ClientProfile).join(ClientProfile, User.id == ClientProfile.user_id)
                .where(User.role == "CLIENT")
                .order_by(User.name)
            )
            rows = result.all()
            logger.info("Fetched %d client rows for CSV export", len(rows))

            output = io.StringIO()
            output.write("ID,Имя,Телефон,Email\n")
            for i, (user, cp) in enumerate(rows):
                output.write(f"{user.id},{user.name},{user.phone},{user.email or ''}\n")
                if (i + 1) % 100 == 0:
                    logger.debug("CSV rows written: %d", i + 1)

            logger.info("Clients CSV export complete: %d rows", len(rows))
            return {
                "filename": f"clients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "content": output.getvalue(),
                "rows": len(rows),
                "media_type": "text/csv; charset=utf-8",
            }

    return _run(_generate())

"""Background export tasks for CSV generation."""
import csv
import io
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def export_appointments_csv_task(
    status: Optional[str] = None,
    include_master: bool = False,
) -> dict:
    """
    Generate appointments CSV in background.
    Returns file content and metadata.
    """
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from app.database import AsyncSessionLocal
    from app.models.appointment import Appointment
    from app.models.client_profile import ClientProfile
    from app.models.user import User
    from app.models.service import Service
    from app.models.master_profile import MasterProfile

    async def _generate():
        async with AsyncSessionLocal() as db:
            query = (
                select(Appointment, User.name.label("client_name"), User.phone.label("client_phone"),
                       Service.name.label("service_name"), Service.price.label("service_price"),
                       User.name.label("master_name"))
                .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
                .join(User, ClientProfile.user_id == User.id, isouter=True)
                .join(Service, Appointment.service_id == Service.id, isouter=True)
                .join(MasterProfile, Appointment.master_id == MasterProfile.id, isouter=True)
                .join(User, MasterProfile.user_id == User.id, isouter=True)
                .order_by(Appointment.appointment_date.desc())
            )

            if status:
                query = query.where(Appointment.status == status)

            result = await db.execute(query)
            rows = result.all()

            output = io.StringIO()
            output.write("ID,Дата,Клиент,Телефон,Услуга,Цена,Статус,Примечания")
            if include_master:
                output.write(",Мастер")
            output.write("\n")

            for row in rows:
                a = row[0]
                line = (
                    f"{a.id},{a.appointment_date.strftime('%Y-%m-%d %H:%M') if a.appointment_date else ''},"
                    f"{row[1] or ''},{row[2] or ''},{row[3] or ''},"
                    f"{float(row[4]) if row[4] else 0},{a.status},{a.notes or ''}"
                )
                if include_master:
                    line += f",{row[5] or ''}"
                output.write(line + "\n")

            return {
                "filename": f"appointments_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "content": output.getvalue(),
                "rows": len(rows),
                "media_type": "text/csv; charset=utf-8",
            }

    import asyncio
    return asyncio.run(_generate())


def export_clients_csv_task() -> dict:
    """Generate clients CSV in background."""
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.user import User
    from app.models.client_profile import ClientProfile

    async def _generate():
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User, ClientProfile).join(ClientProfile, User.id == ClientProfile.user_id)
                .where(User.role == "CLIENT")
                .order_by(User.name)
            )
            rows = result.all()

            output = io.StringIO()
            output.write("ID,Имя,Телефон,Email\n")
            for user, cp in rows:
                output.write(f"{user.id},{user.name},{user.phone},{user.email or ''}\n")

            return {
                "filename": f"clients_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "content": output.getvalue(),
                "rows": len(rows),
                "media_type": "text/csv; charset=utf-8",
            }

    import asyncio
    return asyncio.run(_generate())

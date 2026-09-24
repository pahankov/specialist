"""Admin CSV export endpoints with background task support."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.user import User
from app.models.service import Service
from app.models.master_profile import MasterProfile
from app.dependencies.auth import require_master
from app.services.background_tasks import bg_task_service
from app.services.export_tasks import export_appointments_csv_task, export_clients_csv_task

router = APIRouter()


@router.get("/export/appointments")
async def export_appointments_csv(
    master: User = Depends(require_master),
    status: Optional[str] = Query(None),
    background: bool = Query(False, description="Run in background"),
    db: AsyncSession = Depends(get_db)
):
    """Export appointments to CSV.
    
    Use ?background=true to run in background and get job_id.
    """
    if background:
        job_id = bg_task_service.enqueue(
            export_appointments_csv_task,
            status=status,
            include_master=master.is_admin,
        )
        return {
            "message": "Export started in background",
            "job_id": job_id,
            "status_url": f"/api/v1/admin/export/appointments/status/{job_id}"
        }

    # Synchronous export
    query = (
        select(Appointment, User.name.label('client_name'), User.phone.label('client_phone'),
               Service.name.label('service_name'), Service.price.label('service_price'))
        .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
        .join(User, ClientProfile.user_id == User.id, isouter=True)
        .join(Service, Appointment.service_id == Service.id, isouter=True)
        .where(Appointment.master_id == master.master_profile.id)
    )
    if status:
        query = query.where(Appointment.status == status)
    query = query.order_by(Appointment.appointment_date.desc())
    result = await db.execute(query)
    rows = result.all()
    lines = ["ID,Дата,Клиент,Телефон,Услуга,Цена,Статус,Примечания"]
    for row in rows:
        a = row[0]
        lines.append(
            f"{a.id},{a.appointment_date.strftime('%Y-%m-%d %H:%M') if a.appointment_date else ''},"
            f"{row[1] or ''},{row[2] or ''},{row[3] or ''},"
            f"{float(row[4]) if row[4] else 0},{a.status},{a.notes or ''}"
        )
    return Response(
        content="\n".join(lines) + "\n",
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=appointments.csv'}
    )


@router.get("/export/appointments/status/{job_id}")
async def get_export_status(
    job_id: str,
    master: User = Depends(require_master)
):
    """Get status of a background export task."""
    status = bg_task_service.get_job_status(job_id)
    if status is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found or background tasks disabled")
    return status


@router.get("/export/clients")
async def export_clients_csv(
    master: User = Depends(require_master),
    background: bool = Query(False, description="Run in background"),
    db: AsyncSession = Depends(get_db)
):
    """Export all clients to CSV.
    
    Use ?background=true to run in background.
    """
    if background:
        job_id = bg_task_service.enqueue(export_clients_csv_task)
        return {
            "message": "Export started in background",
            "job_id": job_id,
            "status_url": f"/api/v1/admin/export/clients/status/{job_id}"
        }

    # Synchronous export
    result = await db.execute(
        select(User, ClientProfile).join(ClientProfile, User.id == ClientProfile.user_id)
        .where(User.role == "CLIENT")
        .order_by(User.name)
    )
    rows = result.all()
    lines = ["ID,Имя,Телефон,Email"]
    for user, cp in rows:
        lines.append(f"{user.id},{user.name},{user.phone},{user.email or ''}")
    return Response(
        content="\n".join(lines) + "\n",
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=clients.csv'}
    )


@router.get("/export/clients/status/{job_id}")
async def get_clients_export_status(
    job_id: str,
    master: User = Depends(require_master)
):
    """Get status of a background clients export task."""
    status = bg_task_service.get_job_status(job_id)
    if status is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Task not found or background tasks disabled")
    return status


@router.get("/export/stats")
async def get_export_stats(
    master: User = Depends(require_master)
):
    """Get background task queue statistics."""
    return bg_task_service.get_queue_stats()

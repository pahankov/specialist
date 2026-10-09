"""Admin CSV export endpoints with background task support."""
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import aliased
from typing import Optional

from app.database import get_db
from app.models.appointment import Appointment
from app.models.client_profile import ClientProfile
from app.models.user import User, UserRole
from app.models.service import Service
from app.models.master_profile import MasterProfile
from app.dependencies.auth import require_master, require_super_admin
from app.services.background_tasks import bg_task_service
from app.services.export_tasks import export_appointments_csv_task, export_clients_csv_task
from app.modules.admin.helpers import get_master_profile_id

router = APIRouter()

# Aliases for the same table joined multiple times
_ClientUser = aliased(User, name="client_user")
_MasterUser = aliased(User, name="master_user")


@router.get("/export/appointments")
async def export_appointments_csv(
    master: User = Depends(require_master),
    status: Optional[str] = Query(None),
    background: bool = Query(False, description="Run in background"),
    include_master: bool = Query(False, description="Include master name column"),
    master_id: Optional[int] = Query(None, description="MasterProfile.id scope (superadmin only)"),
    ids: Optional[str] = Query(None, description="Comma-separated appointment ids (selection export)"),
    db: AsyncSession = Depends(get_db)
):
    """Export appointments to CSV.

    Use ?background=true to run in background and get job_id.
    Superadmin exports everything unless master_id/ids scope it;
    regular masters export only their own.
    """
    if background:
        job_id = bg_task_service.enqueue(
            export_appointments_csv_task,
            status=status,
            include_master=include_master or master.is_admin,
        )
        return {
            "message": "Export started in background",
            "job_id": job_id,
            "status_url": f"/api/v1/admin/export/appointments/status/{job_id}"
        }

    # Synchronous export
    is_admin = master.role == UserRole.ADMIN
    if is_admin:
        mp_id = master_id
    else:
        mp_id = await get_master_profile_id(db, master)
    query = (
        select(Appointment, _ClientUser.name.label('client_name'), _ClientUser.phone.label('client_phone'),
               Service.name.label('service_name'), Service.price.label('service_price'),
               _MasterUser.name.label('master_name'))
        .join(ClientProfile, Appointment.client_id == ClientProfile.id, isouter=True)
        .join(_ClientUser, ClientProfile.user_id == _ClientUser.id, isouter=True)
        .join(Service, Appointment.service_id == Service.id, isouter=True)
        .join(MasterProfile, Appointment.master_id == MasterProfile.id, isouter=True)
        .join(_MasterUser, MasterProfile.user_id == _MasterUser.id, isouter=True)
    )
    if mp_id is not None:
        query = query.where(Appointment.master_id == mp_id)
    if ids:
        wanted = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if wanted:
            query = query.where(Appointment.id.in_(wanted))
    if status:
        query = query.where(Appointment.status == status)
    query = query.order_by(Appointment.appointment_date.desc())
    result = await db.execute(query)
    rows = result.all()
    header = "ID,Дата,Клиент,Телефон,Услуга,Цена,Статус,Примечания"
    if include_master:
        header += ",Мастер"
    lines = [header]
    for row in rows:
        a = row[0]
        line = (
            f"{a.id},{a.appointment_date.strftime('%Y-%m-%d %H:%M') if a.appointment_date else ''},"
            f"{row[1] or ''},{row[2] or ''},{row[3] or ''},"
            f"{float(row[4]) if row[4] else 0},{a.status},{a.notes or ''}"
        )
        if include_master:
            line += f",{row[5] or ''}"
        lines.append(line)
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
    ids: Optional[str] = Query(None, description="Comma-separated user ids (selection export)"),
    search: Optional[str] = Query(None, description="Filter by name or phone"),
    master_id: Optional[int] = Query(None, description="Only clients of this master"),
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
    client_query = (
        select(User, ClientProfile).join(ClientProfile, User.id == ClientProfile.user_id)
        .where(User.role == "CLIENT")
        .order_by(User.name)
    )
    if ids:
        wanted = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if wanted:
            client_query = client_query.where(User.id.in_(wanted))
    else:
        if master_id is not None:
            client_query = client_query.where(
                ClientProfile.id.in_(
                    select(Appointment.client_id).where(Appointment.master_id == master_id)
                )
            )
        if search:
            search_term = f"%{search}%"
            client_query = client_query.where(
                (User.name.ilike(search_term)) | (User.phone.ilike(search_term))
            )
    result = await db.execute(client_query)
    rows = result.all()
    from app.models.city import City
    city_ids = {u.city_id for u, _ in rows if u.city_id is not None}
    city_names: dict = {}
    if city_ids:
        city_rows = await db.execute(
            select(City.id, City.name_ru).where(City.id.in_(city_ids))
        )
        city_names = dict(city_rows.all())
    lines = ["ID,Имя,Телефон,Email,Город"]
    for user, cp in rows:
        lines.append(
            f"{user.id},{user.name},{user.phone},{user.email or ''}"
            f",{city_names.get(user.city_id, '')}"
        )
    return Response(
        content="\n".join(lines) + "\n",
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=clients.csv'}
    )


@router.get("/export/masters")
async def export_masters_csv(
    admin: User = Depends(require_super_admin),
    ids: Optional[str] = Query(None, description="Comma-separated master user ids (selection export)"),
    db: AsyncSession = Depends(get_db)
):
    """Export all masters to CSV (superadmin only)."""
    from app.models.city import City
    masters_query = (
        select(User, MasterProfile)
        .join(MasterProfile, User.id == MasterProfile.user_id)
        .order_by(User.name)
    )
    if ids:
        wanted = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        if wanted:
            masters_query = masters_query.where(User.id.in_(wanted))
    result = await db.execute(masters_query)
    rows = result.all()
    city_ids = {u.city_id for u, _ in rows if u.city_id is not None}
    city_names: dict = {}
    if city_ids:
        city_rows = await db.execute(
            select(City.id, City.name_ru).where(City.id.in_(city_ids))
        )
        city_names = dict(city_rows.all())
    lines = ["ID,Имя,Email,Телефон,Telegram,Статус,Активен,Тариф,Триал до,Город"]
    for user, mp in rows:
        trial = mp.trial_ends_at.strftime('%Y-%m-%d') if mp.trial_ends_at else ''
        lines.append(
            f"{user.id},{user.name},{user.email or ''},{user.phone or ''}"
            f",{mp.telegram_username or ''},{mp.status},{user.is_active}"
            f",{mp.tariff or ''},{trial},{city_names.get(user.city_id, '')}"
        )
    return Response(
        content="\n".join(lines) + "\n",
        media_type='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=masters.csv'}
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

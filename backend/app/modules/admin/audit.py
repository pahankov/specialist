"""Admin audit logs endpoint."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from typing import Optional
from app.modules.admin.base import (
    get_db, AuditLog, Master, require_master, AuditLogListResponse, AuditLogResponse
)
from app.modules.auth.dependencies import require_super_admin

router = APIRouter()


def _build_log_response(log: AuditLog) -> AuditLogResponse:
    """Build AuditLogResponse with master name from relationship."""
    return AuditLogResponse(
        id=log.id,
        master_id=log.master_id,
        master_name=log.master.name if log.master else None,
        level=log.level,
        action=log.action,
        entity_type=log.entity_type,
        entity_id=log.entity_id,
        details=log.details,
        ip_address=log.ip_address,
        created_at=log.created_at
    )


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def get_audit_logs(
    master: Master = Depends(require_master),
    entity_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs for the authenticated master."""
    query = select(AuditLog).where(AuditLog.master_id == master.id)
    count_query = select(func.count(AuditLog.id)).where(AuditLog.master_id == master.id)
    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    query = query.options(selectinload(AuditLog.master)).order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    return AuditLogListResponse(
        total=total,
        logs=[_build_log_response(log) for log in logs]
    )


@router.get("/audit-logs/all", response_model=AuditLogListResponse)
async def get_all_audit_logs(
    super_admin: Master = Depends(require_super_admin),
    entity_type: Optional[str] = Query(None),
    master_id: Optional[int] = Query(None, description="Filter by master ID"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get ALL audit logs (superadmin only)."""
    query = select(AuditLog).options(selectinload(AuditLog.master))
    count_query = select(func.count(AuditLog.id))

    if entity_type:
        query = query.where(AuditLog.entity_type == entity_type)
        count_query = count_query.where(AuditLog.entity_type == entity_type)
    if master_id:
        query = query.where(AuditLog.master_id == master_id)
        count_query = count_query.where(AuditLog.master_id == master_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0
    query = query.order_by(AuditLog.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    logs = result.scalars().all()
    return AuditLogListResponse(
        total=total,
        logs=[_build_log_response(log) for log in logs]
    )

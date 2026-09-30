"""Audit logs for masters."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from typing import Optional

from app.database import get_db
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.pagination import PaginatedResponse
from app.dependencies.auth import require_super_admin

router = APIRouter()


@router.get("/audit-logs")
async def get_master_audit_logs(
    master_id: int = Query(None, description="Filter by master ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=200, description="Items per page"),
    super_admin: User = Depends(require_super_admin),
    db: AsyncSession = Depends(get_db)
):
    """Get audit logs, optionally filtered by master_id."""
    offset = (page - 1) * page_size

    base_query = select(AuditLog)
    count_query = select(func.count(AuditLog.id))

    if master_id is not None:
        base_query = base_query.where(AuditLog.master_id == master_id)
        count_query = count_query.where(AuditLog.master_id == master_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    data_query = (
        base_query
        .options(selectinload(AuditLog.user))
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    result = await db.execute(data_query)
    logs = result.scalars().all()

    items = [
        {
            "id": log.id,
            "master_id": log.master_id,
            "master_name": log.user.name if log.user else None,
            "level": log.level,
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size if page_size > 0 else 0
    )

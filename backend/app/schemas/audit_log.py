from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class AuditLogResponse(BaseModel):
    id: int
    master_id: Optional[int] = None
    master_name: Optional[str] = None
    level: Optional[str] = "info"
    action: str
    entity_type: str
    entity_id: Optional[int] = None
    details: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditLogListResponse(BaseModel):
    total: int
    logs: list[AuditLogResponse]

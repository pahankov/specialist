from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class BlockedSlotCreate(BaseModel):
    master_id: int
    start_dt: datetime
    end_dt: datetime
    reason: Optional[str] = None


class BlockedSlotResponse(BaseModel):
    id: int
    master_id: int
    start_dt: datetime
    end_dt: datetime
    reason: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

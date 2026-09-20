from datetime import time
from pydantic import BaseModel, ConfigDict, field_serializer
from typing import Optional

class WorkingHourCreate(BaseModel):
    schedule_date: str  # YYYY-MM-DD
    start_time: str
    end_time: str

class WorkingHourUpdate(BaseModel):
    schedule_date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class WorkingHourResponse(BaseModel):
    id: int
    master_id: int
    schedule_date: str
    start_time: time
    end_time: time
    
    @field_serializer('start_time', 'end_time')
    def serialize_time(self, value: time | None) -> str | None:
        return value.strftime('%H:%M:%S') if value else None
    
    model_config = ConfigDict(from_attributes=True)

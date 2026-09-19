from pydantic import BaseModel
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
    start_time: str
    end_time: str
    
    class Config:
        from_attributes = True

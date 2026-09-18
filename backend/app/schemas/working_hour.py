from pydantic import BaseModel
from typing import Optional

class WorkingHourCreate(BaseModel):
    date: str  # YYYY-MM-DD
    start_time: str
    end_time: str

class WorkingHourUpdate(BaseModel):
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

class WorkingHourResponse(BaseModel):
    id: int
    master_id: int
    date: str
    start_time: str
    end_time: str
    
    class Config:
        from_attributes = True

from pydantic import BaseModel
from datetime import time

class WorkingHourCreate(BaseModel):
    master_id: int
    day_of_week: int
    start_time: str
    end_time: str

class WorkingHourResponse(BaseModel):
    id: int
    master_id: int
    day_of_week: int
    start_time: str
    end_time: str
    class Config:
        from_attributes = True
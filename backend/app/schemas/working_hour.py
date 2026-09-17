from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import time


class WorkingHourCreate(BaseModel):
    day_of_week: int
    start_time: str
    end_time: str

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: int) -> int:
        if v < 0 or v > 6:
            raise ValueError("day_of_week must be 0-6 (Monday-Sunday)")
        return v


class WorkingHourUpdate(BaseModel):
    day_of_week: Optional[int] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    @field_validator("day_of_week")
    @classmethod
    def validate_day(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and (v < 0 or v > 6):
            raise ValueError("day_of_week must be 0-6 (Monday-Sunday)")
        return v


class WorkingHourResponse(BaseModel):
    id: int
    master_id: int
    day_of_week: int
    start_time: str
    end_time: str

    @field_validator("start_time", "end_time", mode="before")
    @classmethod
    def time_to_str(cls, v):
        if isinstance(v, time):
            return v.isoformat()
        return v

    class Config:
        from_attributes = True

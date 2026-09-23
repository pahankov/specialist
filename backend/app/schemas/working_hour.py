from datetime import date, time
from pydantic import BaseModel, ConfigDict, field_serializer, field_validator
from typing import Optional

class WorkingHourCreate(BaseModel):
    schedule_date: date
    start_time: time
    end_time: time

    @field_validator('schedule_date', mode='before')
    @classmethod
    def parse_date(cls, v):
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            return date.fromisoformat(v)
        raise ValueError('Invalid date format')

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def parse_time(cls, v):
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            parts = v.split(':')
            return time(int(parts[0]), int(parts[1]))
        raise ValueError('Invalid time format')

class WorkingHourUpdate(BaseModel):
    schedule_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None

    @field_validator('schedule_date', mode='before')
    @classmethod
    def parse_date(cls, v):
        if v is None:
            return v
        if isinstance(v, date):
            return v
        if isinstance(v, str):
            return date.fromisoformat(v)
        raise ValueError('Invalid date format')

    @field_validator('start_time', 'end_time', mode='before')
    @classmethod
    def parse_time(cls, v):
        if v is None:
            return v
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            parts = v.split(':')
            return time(int(parts[0]), int(parts[1]))
        raise ValueError('Invalid time format')

class WorkingHourResponse(BaseModel):
    id: int
    master_id: int
    schedule_date: date
    start_time: time
    end_time: time
    
    @field_serializer('schedule_date')
    def serialize_date(self, value: date) -> str:
        return value.isoformat()
    
    @field_serializer('start_time', 'end_time')
    def serialize_time(self, value: time | None) -> str | None:
        return value.strftime('%H:%M:%S') if value else None
    
    model_config = ConfigDict(from_attributes=True)

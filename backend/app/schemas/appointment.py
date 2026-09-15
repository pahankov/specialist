from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AppointmentCreate(BaseModel):
    master_id: int
    service_id: int
    client_name: str
    client_phone: str
    appointment_date: datetime

class AppointmentResponse(BaseModel):
    id: int
    master_id: int
    service_id: int
    client_id: Optional[int]
    appointment_date: datetime
    status: str
    notes: Optional[str]
    class Config:
        from_attributes = True

class AvailableDay(BaseModel):
    date: str
    day_of_week: int

class AvailableSlot(BaseModel):
    start: datetime
    end: datetime

class PublicBookingCreate(BaseModel):
    master_id: int
    service_id: int
    client_name: str
    client_phone: str
    appointment_date: datetime
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

class AppointmentCreate(BaseModel):
    master_id: int
    service_id: int
    client_name: str
    client_phone: str
    appointment_date: datetime
    notes: Optional[str] = None

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

class AppointmentWithDetails(BaseModel):
    id: int
    master_id: int
    service_id: int
    client_id: Optional[int]
    appointment_date: datetime
    status: str
    notes: Optional[str]
    client_name: Optional[str]
    client_phone: Optional[str]
    service_name: Optional[str]
    service_price: Optional[Decimal]
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
    notes: Optional[str] = None


class AdminBookingCreate(BaseModel):
    client_id: int
    service_id: int
    appointment_date: datetime
    status: str = "pending"
    notes: Optional[str] = None
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class ServiceCreate(BaseModel):
    master_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    duration_minutes: int
    price: Decimal

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[Decimal] = None

class ServiceResponse(BaseModel):
    id: int
    master_id: int
    name: str
    description: Optional[str]
    duration_minutes: int
    price: Decimal

    class Config:
        from_attributes = True
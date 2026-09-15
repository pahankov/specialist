from pydantic import BaseModel
from typing import Optional
from decimal import Decimal

class ServiceCreate(BaseModel):
    master_id: int
    name: str
    description: Optional[str] = None
    duration_minutes: int
    price: Decimal

class ServiceResponse(BaseModel):
    id: int
    master_id: int
    name: str
    description: Optional[str]
    duration_minutes: int
    price: Decimal

    class Config:
        from_attributes = True
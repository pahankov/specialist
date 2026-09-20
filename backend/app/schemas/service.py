from pydantic import BaseModel, ConfigDict
from typing import Optional
from decimal import Decimal

class ServiceCreate(BaseModel):
    master_id: int
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
    is_active: bool = True

    model_config = ConfigDict(from_attributes=True)
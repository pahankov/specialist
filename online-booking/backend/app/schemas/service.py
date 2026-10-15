from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime
from decimal import Decimal

class ServiceCreate(BaseModel):
    name: str
    description: Optional[str] = None
    duration_minutes: int
    price: Decimal
    master_id: Optional[int] = None
    category: Optional[str] = None
    discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    discount_until: Optional[datetime] = Field(default=None)

class ServiceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    price: Optional[Decimal] = None
    category: Optional[str] = None
    discount_percent: Optional[int] = Field(default=None, ge=0, le=90)
    discount_until: Optional[datetime] = Field(default=None)

class ServiceResponse(BaseModel):
    id: int
    master_id: int
    name: str
    description: Optional[str]
    duration_minutes: int
    # float on the wire (Decimal serializes as a string in JSON and every
    # consumer just wants a number).
    price: float
    category: Optional[str] = None
    is_active: bool = True
    discount_percent: int = 0
    discount_until: Optional[datetime] = None
    effective_price: float = 0

    model_config = ConfigDict(from_attributes=True)
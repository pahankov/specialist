from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class MasterCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    telegram_username: Optional[str] = None

class MasterResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    telegram_username: Optional[str]
    class Config:
        from_attributes = True

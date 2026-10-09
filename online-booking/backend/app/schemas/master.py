from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re

from app.utils.security import validate_password_strength
from app.utils.phone import normalize_phone


class MasterCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    telegram_username: Optional[str] = None
    city_id: Optional[int] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None or v.strip() == '':
            return None
        return normalize_phone(v)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class MasterUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    telegram_username: Optional[str] = None
    description: Optional[str] = None
    password: Optional[str] = None
    tariff: Optional[str] = None
    trial_ends_at: Optional[datetime] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_password_strength(v)


class MasterResponse(BaseModel):
    id: int  # master_profile.id
    user_id: int  # user.id
    name: str
    email: str
    phone: Optional[str]
    telegram_username: Optional[str]
    description: Optional[str]
    status: str
    is_active: bool
    is_admin: bool
    tariff: str = "trial"
    trial_ends_at: Optional[datetime] = None
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

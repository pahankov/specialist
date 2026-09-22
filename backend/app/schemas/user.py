"""Pydantic schemas for User model."""
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole


def normalize_phone(phone: str) -> str:
    """Normalize phone to +7 (XXX) XXX-XX-XX format."""
    import re
    digits = re.sub(r'\D', '', phone)
    if not digits:
        raise ValueError('Введите номер телефона')
    if len(digits) > 11:
        digits = digits[-11:]
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    if not digits.startswith('7'):
        digits = '7' + digits
    if len(digits) != 11:
        raise ValueError('Номер телефона должен содержать 10 цифр')
    return f'+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}'


class UserBase(BaseModel):
    name: str
    role: UserRole
    city_id: Optional[int] = None


class UserCreate(UserBase):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return normalize_phone(v)


class UserLoginByEmail(BaseModel):
    email: str
    password: str


class UserLoginByPhone(BaseModel):
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class UserUpdate(BaseModel):
    name: Optional[str] = None
    city_id: Optional[int] = None
    password: Optional[str] = None


class UserResponse(UserBase):
    id: int
    email: Optional[str] = None
    phone: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UserWithProfileResponse(UserResponse):
    master_profile: Optional[dict] = None
    client_profile: Optional[dict] = None

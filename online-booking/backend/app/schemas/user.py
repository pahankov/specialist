"""Pydantic schemas for User model."""
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional
from datetime import datetime
from app.models.user import UserRole
import re

from app.utils.security import validate_password_strength
from app.utils.phone import normalize_phone


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

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return validate_password_strength(v)


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

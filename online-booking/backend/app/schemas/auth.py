"""Pydantic schemas for authentication."""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from enum import Enum

from app.utils.security import validate_password_strength
from app.utils.phone import normalize_phone


class UserRoleEnum(str, Enum):
    CLIENT = "client"
    MASTER = "master"


class UnifiedLoginRequest(BaseModel):
    """Login with email OR phone + password."""
    identifier: str  # email or phone
    password: str

    @field_validator('identifier')
    @classmethod
    def validate_identifier(cls, v: str) -> str:
        if not v.strip():
            raise ValueError('Введите email или телефон')
        return v.strip()


class UnifiedRegisterRequest(BaseModel):
    """Full registration with role selection."""
    name: str
    email: EmailStr
    phone: str
    password: str
    city_name: Optional[str] = None
    telegram_username: Optional[str] = None
    is_master: bool = False

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)

    @field_validator('telegram_username')
    @classmethod
    def validate_telegram(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if v and not v.startswith('@'):
            v = '@' + v
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    pass  # refresh token comes from cookie

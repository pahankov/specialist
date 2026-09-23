"""Pydantic schemas for authentication."""
from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from enum import Enum


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
    city_id: Optional[int] = None
    telegram_username: Optional[str] = None
    is_master: bool = False

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        import re
        digits = re.sub(r'\D', '', v)
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

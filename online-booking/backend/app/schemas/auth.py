"""Pydantic schemas for authentication."""
from pydantic import BaseModel, field_validator
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
    """Quick registration: phone + password only.

    Everything else (name, email, address, city) is refined later in the
    client cabinet profile — registration stays minimal by design. Every
    account created here is a CLIENT; becoming a master is a separate,
    admin-approved application (/become-master).
    """
    phone: str
    password: str
    # 152-FZ consent checkbox (offer + privacy policy); stamped on the account.
    consent: bool = False

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(v)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenRefreshRequest(BaseModel):
    pass  # refresh token comes from cookie

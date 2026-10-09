"""Pydantic schemas for OTP authentication."""
from pydantic import BaseModel, field_validator
from typing import Optional

from app.utils.phone import normalize_phone


class SendOtpRequest(BaseModel):
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class VerifyOtpRequest(BaseModel):
    phone: str
    code: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Код должен содержать 6 цифр')
        return v


class OtpResponse(BaseModel):
    message: str

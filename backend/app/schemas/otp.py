"""Pydantic schemas for OTP authentication."""
from pydantic import BaseModel, field_validator
from typing import Optional


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

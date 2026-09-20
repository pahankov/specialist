import re
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from typing import Optional
from datetime import datetime


def normalize_phone(phone: str) -> str:
    """Извлекает цифры, нормализует к +7, возвращает формат +7 (XXX) XXX-XX-XX."""
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
        raise ValueError('Номер телефона должен содержать 10 цифр (например 9991234567)')
    return f'+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}'


class MasterCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: str
    telegram_username: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

class MasterUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    telegram_username: Optional[str] = None
    description: Optional[str] = None
    password: Optional[str] = None

class MasterResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: Optional[str]
    telegram_username: Optional[str]
    description: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    model_config = ConfigDict(from_attributes=True)

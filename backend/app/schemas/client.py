import re
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional


def normalize_phone(phone: str) -> str:
    """Извлекает цифры, нормализует к +7, возвращает формат +7 (XXX) XXX-XX-XX."""
    digits = re.sub(r'\D', '', phone)
    if not digits:
        raise ValueError('Введите номер телефона')
    # Слишком много цифр — ошибка
    if len(digits) > 11:
        raise ValueError('Номер телефона содержит слишком много цифр')
    # 8 в начале → 7
    if digits.startswith('8') and len(digits) == 11:
        digits = '7' + digits[1:]
    # Нет 7 в начале → добавляем
    if not digits.startswith('7'):
        digits = '7' + digits
    if len(digits) != 11:
        raise ValueError('Номер телефона должен содержать 10 цифр (например 9991234567)')
    return f'+7 ({digits[1:4]}) {digits[4:7]}-{digits[7:9]}-{digits[9:11]}'


class ClientCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', v):
            raise ValueError('Некорректный email')
        return v


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        return normalize_phone(v)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', v):
            raise ValueError('Некорректный email')
        return v


class ClientResponse(BaseModel):
    id: int
    name: str
    phone: str
    email: Optional[str] = None
    no_show_count: int = 0
    model_config = ConfigDict(from_attributes=True)

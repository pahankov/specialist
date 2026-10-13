import re
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional

from app.utils.phone import normalize_phone


class ClientCreate(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    address: Optional[str] = None

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
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    address: Optional[str] = None

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
    is_active: bool = True
    # Master-scoped blacklist badge (clients list only; default keeps
    # every other producer of this schema unchanged).
    is_blocked: bool = False
    # Archive visibility (master clients list with ?include_hidden=true).
    is_hidden: bool = False
    hidden_reason: Optional[str] = None
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    address: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)

"""Pydantic schemas for client self-service."""
from pydantic import BaseModel, ConfigDict, field_validator
from typing import Optional


class ClientMeResponse(BaseModel):
    id: int
    name: str
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    is_verified: bool = False
    # Bound MAX account (login via chat-bot): id + @nickname for support.
    max_bound: bool = False
    max_username: Optional[str] = None
    # Bound VK ID account (login via VK/OK/Mail widget).
    vk_bound: bool = False
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    address: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ClientMeUpdate(BaseModel):
    name: Optional[str] = None
    last_name: Optional[str] = None
    city_id: Optional[int] = None
    address: Optional[str] = None

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError('Имя не может быть пустым')
        if len(v) > 100:
            raise ValueError('Имя слишком длинное')
        return v

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if len(v) > 500:
            raise ValueError('Адрес слишком длинный')
        return v or None


class FavoriteEntry(BaseModel):
    id: int
    name: Optional[str] = None
    visits: int = 0


class ClientStatsResponse(BaseModel):
    total_spent: float = 0
    completed_visits: int = 0
    upcoming_count: int = 0
    cancelled_count: int = 0
    favorite_master: Optional[FavoriteEntry] = None
    favorite_service: Optional[FavoriteEntry] = None

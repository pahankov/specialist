"""Pydantic schemas for MAX chat-bot auth."""
from pydantic import BaseModel, field_validator
from typing import Literal, Optional

from app.utils.phone import normalize_phone


class MaxStartRequest(BaseModel):
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class MaxStartResponse(BaseModel):
    code: str  # shown on site; user retypes it to the MAX bot
    expires_in: int  # seconds
    bot_username: str
    bot_url: str


class MaxStatusRequest(BaseModel):
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class MaxStatusResponse(BaseModel):
    status: Literal["pending", "verified", "expired", "disabled"]
    access_token: Optional[str] = None
    token_type: str = "bearer"
    is_new_user: Optional[bool] = None

"""Pydantic schemas for MAX chat-bot auth (SMS-style flow)."""
from pydantic import BaseModel, field_validator
from typing import Optional

from app.utils.phone import normalize_phone


class MaxStartRequest(BaseModel):
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class MaxStartResponse(BaseModel):
    # NOTE: no code here — bound users get it pushed into their dialog,
    # everyone else receives it after sharing the number with the bot.
    delivered: bool  # True = code already pushed to the known MAX dialog
    expires_in: int  # seconds
    bot_username: str
    bot_url: str


class MaxVerifyRequest(BaseModel):
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


class MaxVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: Optional[bool] = None

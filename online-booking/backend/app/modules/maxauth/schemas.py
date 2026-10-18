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
    # NOTE: no code here — bound users get it pushed into their MAX dialog;
    # everyone else receives it in the dialog after «Поделиться номером»
    # (the platform proves the number belongs to that MAX account).
    delivered: bool  # True = code already pushed to the known MAX dialog
    deeplink: str  # one-click bot URL with request payload ("" if unconfigured)
    expires_in: int  # seconds
    bot_username: str
    bot_url: str
    bot_name: str  # human-readable name for the site button (falls back to username)


class MaxVerifyRequest(BaseModel):
    phone: str
    code: str
    # 152-FZ consent checkbox on the MAX login form (offer + privacy policy).
    # Stamped on account creation / backfilled onto legacy NULL-consent users.
    consent: bool = False

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

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
    """Login/Signup with email OR phone + password.

    ``consent`` stays false on the first attempt. When nothing matches the
    identifier, the backend answers 401 with ``detail.code ==
    "registration_required"``; the frontend collects the 152-FZ consent and
    retries with ``consent=true`` — the cabinet is then created on the fly
    (unverified data, refined later in the profile).
    """
    identifier: str  # email or phone
    password: str
    consent: bool = False

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
    account created here is a CLIENT; becoming a master is a separate
    self-service draft with immediate activation (/become-master).

    For the 2-step consent flow (1.80.0), the frontend sends a ``challenge``
    token (from /phone/status) instead of ``phone`` — the phone is embedded
    in the challenge and validated server-side.
    """
    phone: Optional[str] = None
    password: str
    # 152-FZ consent checkbox (offer + privacy policy); stamped on the account.
    consent: bool = False
    # Challenge token from the 2-step flow (phone/status). When present,
    # ``phone`` is ignored and the phone is extracted from the challenge.
    challenge: Optional[str] = None

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


# ─── Password management (1.79.0) ────────────────────────────────────

def _clean_email(v: str) -> str:
    v = (v or "").strip().lower()
    if "@" not in v or v.startswith("@") or v.endswith("@"):
        raise ValueError('Введите корректный email')
    return v


class ChangePasswordRequest(BaseModel):
    """Change the current account's password (any role that has one)."""
    current_password: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


class ForgotPasswordRequest(BaseModel):
    """«Забыли пароль»: a reset code is emailed to the account address."""
    email: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _clean_email(v)


class ResetPasswordRequest(BaseModel):
    """Finish the reset: the emailed code + the new password."""
    email: str
    code: str
    new_password: str

    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        return _clean_email(v)

    @field_validator('code')
    @classmethod
    def validate_code(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 6:
            raise ValueError('Код должен содержать 6 цифр')
        return v

    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return validate_password_strength(v)


# ─── Unified entry (1.79.0) ──────────────────────────────────────────

class PhoneStatusRequest(BaseModel):
    """First step of the unified entry: what awaits this phone number."""
    phone: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return normalize_phone(v)


class PhoneStatusResponse(BaseModel):
    """Unified-entry hint for one phone («Единый вход», шаг 1).

    state: "new"      — no account: offer phone+password signup;
           "password" — an account with a password: ask for it;
           "social"   — an account without a password: VK/Яндекс/MAX entry.
    """
    state: str
    phone: str  # normalized, echoed back for the next step
    # Challenge token for the 2-step consent flow (1.80.0). Present only
    # when state="new" — the frontend shows the register form, then calls
    # /auth/consent/complete with this challenge + the user's consent.
    challenge: Optional[str] = None

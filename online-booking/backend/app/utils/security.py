"""Password hashing utilities (bcrypt).

Single home for password helpers — modules, scripts and tests import from
here instead of reaching into app.modules.auth.service (module->module
imports violate the modular architecture).
"""
import bcrypt
import hashlib


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt directly (avoids passlib incompatibility)."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def hash_password(password: str) -> str:
    """Hash password using bcrypt directly (avoids passlib incompatibility)."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def validate_password_strength(password: str) -> str:
    """Enforce the platform password policy. Returns password or raises ValueError.

    Single source of truth — used by pydantic schemas and admin endpoints.
    """
    if len(password) < 8:
        raise ValueError("Пароль должен содержать минимум 8 символов")
    if not any(c.isupper() for c in password):
        raise ValueError("Пароль должен содержать хотя бы одну заглавную букву")
    if not any(c.islower() for c in password):
        raise ValueError("Пароль должен содержать хотя бы одну строчную букву")
    if not any(c.isdigit() for c in password):
        raise ValueError("Пароль должен содержать хотя бы одну цифру")
    if not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
        raise ValueError("Пароль должен содержать хотя бы один спецсимвол")
    if len(set(password)) < 4:
        raise ValueError("Пароль должен содержать минимум 4 уникальных символа")
    return password


def hash_otp_code(code: str) -> str:
    """Hash an OTP/MAX code for secure storage (sha256, codes are short-lived)."""
    return hashlib.sha256(code.encode()).hexdigest()

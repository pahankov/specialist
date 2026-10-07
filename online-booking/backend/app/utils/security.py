"""Password hashing utilities (bcrypt).

Single home for password helpers — modules, scripts and tests import from
here instead of reaching into app.modules.auth.service (module->module
imports violate the modular architecture).
"""
import bcrypt


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

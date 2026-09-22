"""JWT token creation and validation utilities."""
from datetime import datetime, timedelta, timezone as dt_timezone
import secrets
from app.config import settings

ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS
SECRET_KEY = settings.SECRET_KEY
REFRESH_SECRET_KEY = settings.REFRESH_SECRET_KEY
ALGORITHM = settings.ALGORITHM


def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    expire = (datetime.now(dt_timezone.utc) +
              (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)))
    to_encode.update({"exp": expire})
    return __encode_jwt(to_encode, SECRET_KEY)


def create_refresh_token_payload(master_id: int, email: str) -> tuple[str, datetime]:
    to_encode = {
        "sub": str(master_id),
        "email": email,
        "type": "refresh",
        "jti": secrets.token_urlsafe(32),
    }
    expire = datetime.now(dt_timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode["exp"] = expire
    return __encode_jwt(to_encode, REFRESH_SECRET_KEY), expire


def __encode_jwt(data: dict, secret_key: str) -> str:
    from jose import jwt
    return jwt.encode(data, secret_key, algorithm=ALGORITHM)

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import os
import sys


def _get_default_db_url() -> str:
    """Return PostgreSQL URL for production, SQLite only for local dev."""
    env = os.getenv("APP_ENV", "development")
    if env == "production":
        return os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg2://postgres:postgres@localhost:5432/online_booking"
        )
    # Development: prefer PostgreSQL if available, fall back to SQLite
    pg_url = os.getenv("DATABASE_URL")
    if pg_url:
        return pg_url
    return "sqlite+aiosqlite:///./online_booking.db"


class Settings(BaseSettings):
    DATABASE_URL: str = ""  # set via _get_default_db_url after init
    SECRET_KEY: str = ""
    REFRESH_SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # shortened from 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    APP_NAME: str = "Online Booking API"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    APP_ENV: str = "development"

    # SMS settings
    SMS_PROVIDER: str = "fake"  # "fake" | "twilio" | "smsc"
    SMS_CODE_TTL_SECONDS: int = 300  # 5 minutes
    SMS_MAX_ATTEMPTS: int = 3

    # Twilio (if SMS_PROVIDER=twilio)
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""

    # SMS.ru (if SMS_PROVIDER=smsc)
    SMSC_LOGIN: str = ""
    SMSC_PASSWORD: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.DATABASE_URL:
            self.DATABASE_URL = _get_default_db_url()

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    def validate_secrets(self) -> None:
        """Validate that required secrets are set in production."""
        if self.APP_ENV == "production":
            bad_keys = [
                "dev-secret-key",
                "dev-refresh-secret-key",
            ]
            for key in bad_keys:
                if key in self.SECRET_KEY or key in self.REFRESH_SECRET_KEY:
                    print(
                        f"ERROR: {key} detected in production. "
                        "Set SECRET_KEY and REFRESH_SECRET_KEY via environment variables.",
                        file=sys.stderr,
                    )
                    sys.exit(1)


settings = Settings()
settings.validate_secrets()

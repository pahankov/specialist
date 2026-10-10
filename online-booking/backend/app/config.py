from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
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
    DATABASE_URL: str = Field(default_factory=_get_default_db_url)
    SECRET_KEY: str = ""
    REFRESH_SECRET_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # shortened from 1440
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    APP_NAME: str = "Online Booking API"
    DEBUG: bool = True
    # Logging: explicit level wins, otherwise INFO in production, DEBUG locally
    LOG_LEVEL: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    APP_ENV: str = "development"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

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

    # MAX messenger bot (chat-bot auth as SMS alternative; server-side only)
    MAX_BOT_TOKEN: str = ""
    MAX_BOT_USERNAME: str = ""
    MAX_BOT_URL: str = ""
    MAX_WEBHOOK_SECRET: str = ""

    # DaData (address suggestions; secret never leaves the backend proxy)
    DADATA_API_KEY: str = ""
    DADATA_SECRET: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def log_level(self) -> str:
        if self.LOG_LEVEL:
            return self.LOG_LEVEL.upper()
        return "INFO" if self.APP_ENV == "production" else "DEBUG"

    @property
    def max_enabled(self) -> bool:
        """MAX chat-bot auth available iff bot token is configured."""
        return bool(self.MAX_BOT_TOKEN)

    def validate_secrets(self) -> None:
        """Fail-closed проверка секретов.

        Production: пустой/короткий/дефолтный SECRET_KEY или REFRESH_SECRET_KEY —
        немедленный выход (лучше упасть на старте, чем подписать JWT пустым ключом).
        Development: разрешены dev-значения, но пустые ключи тоже запрещены
        (иначе dev и prod ведут себя по-разному и баги переезжают молча).
        """
        dev_markers = (
            "dev-secret-key",
            "dev-refresh-secret-key",
            "change-in-production",
        )
        for field in ("SECRET_KEY", "REFRESH_SECRET_KEY"):
            value = getattr(self, field, "") or ""
            if not value:
                print(
                    f"ERROR: {field} is empty. "
                    "Set it in online-booking/backend/.env (single runtime canon, see docs/SECRETS.md). "
                    'Generate: python -c "import secrets; print(secrets.token_urlsafe(32))"',
                    file=sys.stderr,
                )
                sys.exit(1)
            if len(value) < 32:
                print(
                    f"ERROR: {field} is too short ({len(value)} chars, need >= 32). "
                    "Generate a strong value, see docs/SECRETS.md.",
                    file=sys.stderr,
                )
                sys.exit(1)
            if self.APP_ENV == "production" and any(m in value for m in dev_markers):
                print(
                    f"ERROR: dev default detected in {field} while APP_ENV=production. "
                    "Set SECRET_KEY and REFRESH_SECRET_KEY via environment variables.",
                    file=sys.stderr,
                )
                sys.exit(1)


settings = Settings()
settings.validate_secrets()

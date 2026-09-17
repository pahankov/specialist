from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./sugar_booking.db"
    SECRET_KEY: Optional[str] = "dev-secret-key-change-in-production"
    REFRESH_SECRET_KEY: Optional[str] = "dev-refresh-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    APP_NAME: str = "Sugar Booking API"
    DEBUG: bool = True
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    class Config:
        env_file = ".env"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

settings = Settings()

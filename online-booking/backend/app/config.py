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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    # Support sessions are intentionally short-lived: a leaked impersonation
    # token must not stay valid for the regular 24-hour access-token window.
    IMPERSONATION_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"
    APP_NAME: str = "Beauty Specialist API"
    DEBUG: bool = True
    # Logging: explicit level wins, otherwise INFO in production, DEBUG locally
    LOG_LEVEL: str = ""
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    APP_ENV: str = "development"

    # Sentry — error tracking (empty = disabled)
    SENTRY_DSN: str = ""

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
    # Human-readable bot name for the site button («Открыть бота …»).
    # Branding text, not a secret; empty falls back to MAX_BOT_USERNAME.
    MAX_BOT_NAME: str = "Электронная запись"
    MAX_WEBHOOK_SECRET: str = ""
    # Public webhook URL (prod only): enables the self-healing subscription
    # guard (app/services/max_webhook_guard.py). Empty = guard off, so dev
    # machines sharing the bot token never touch the prod subscription.
    MAX_WEBHOOK_URL: str = ""
    # Custom CA bundle for platform-api2.max.ru (Russian trusted CA).
    # Empty = backend/certs/russian_trusted_ca.pem if present, else system store.
    MAX_CA_BUNDLE: str = ""

    # VK ID (OAuth 2.0 Authorization Code + PKCE; server-side code exchange).
    # client_id + service_token live in the VK ID app settings; redirect_uri
    # must be registered as a trusted redirect URL.
    #
    # NOTE the VK credential naming (easy to mix up):
    # - VK_CLIENT_ID        = «ID приложения»
    # - VK_SERVICE_TOKEN    = «Сервисный ключ доступа» — this is the
    #   `service_token` POST param VK requires from CONFIDENTIAL apps when
    #   exchanging the code. NOT the «Защищённый ключ» (classic VK API secret).
    VK_CLIENT_ID: str = ""
    VK_SERVICE_TOKEN: str = ""
    # Registered redirect URL — the frontend /auth/vk/callback page.
    VK_REDIRECT_URI: str = ""
    # Space-separated scopes; empty = VK default set (vkid.personal_info:
    # name, surname, sex, photo, birthday). Add "email phone" only when those
    # access rights are enabled for the app in the VK ID admin panel.
    VK_SCOPE: str = ""

    # Yandex ID (OAuth 2.0 Authorization Code; server-side code exchange).
    # Unlike VK there is no PKCE — the exchange uses the app's OAuth secret,
    # which never leaves the backend. redirect_uri must be registered in the
    # Yandex app settings («Платформы приложений → Веб-сервисы → Redirect URI»).
    # - YANDEX_CLIENT_ID     = «ID приложения»
    # - YANDEX_CLIENT_SECRET = «Пароль приложения» (the OAuth client secret)
    YANDEX_CLIENT_ID: str = ""
    YANDEX_CLIENT_SECRET: str = ""
    # Registered redirect URL — the frontend /auth/yandex/callback page.
    YANDEX_REDIRECT_URI: str = ""
    # Space-separated scopes; empty = Yandex default (login:info + login:email).
    YANDEX_SCOPE: str = ""
    # Suggest helper page for the official instant-auth widget
    # («мгновенная авторизация», sdk-suggest.js): receives the OAuth token
    # from Yandex and postMessages it back to the site. Its URL must be
    # registered in the app's Redirect URI list verbatim. Empty = widget off,
    # the frontend keeps the plain redirect button.
    YANDEX_SUGGEST_REDIRECT_URI: str = ""

    # Public site URL used in external notification links (email / MAX / VK).
    PUBLIC_BASE_URL: str = "https://beauty-specialist.ru"
    # VK community access token for user messages (messages.send). VK ID
    # login does not grant messaging permission by itself: a user must allow
    # messages from the community. Empty = VK delivery unavailable.
    VK_NOTIFY_TOKEN: str = ""
    VK_API_VERSION: str = "5.199"

    # DaData (address suggestions; secret never leaves the backend proxy)
    DADATA_API_KEY: str = ""
    DADATA_SECRET: str = ""

    # Outgoing email (1.79.0): account codes, password reset, email confirm.
    # A regular Yandex mailbox (not Yandex 360): smtp.yandex.ru:465 (SSL) with
    # an APP PASSWORD (пароль приложения), not the account password. Empty
    # user/password = sending disabled: letters are only logged (local dev).
    SMTP_HOST: str = "smtp.yandex.ru"
    SMTP_PORT: int = 465
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    # Sender name shown in mail clients («Электронная запись»); the address
    # defaults to SMTP_USER when SMTP_FROM_EMAIL is empty.
    SMTP_FROM_NAME: str = "Электронная запись"
    SMTP_FROM_EMAIL: str = ""

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

    @property
    def vk_enabled(self) -> bool:
        """VK ID auth available iff client id + redirect uri are configured."""
        return bool(self.VK_CLIENT_ID and self.VK_REDIRECT_URI)

    @property
    def yandex_enabled(self) -> bool:
        """Yandex ID auth available iff client id + secret + redirect uri are set."""
        return bool(
            self.YANDEX_CLIENT_ID
            and self.YANDEX_CLIENT_SECRET
            and self.YANDEX_REDIRECT_URI
        )

    @property
    def smtp_enabled(self) -> bool:
        """Outgoing email available iff the sender account is configured."""
        return bool(self.SMTP_USER and self.SMTP_PASSWORD)

    @property
    def vk_notify_enabled(self) -> bool:
        """VK user messages available iff a community token is configured."""
        return bool(self.VK_NOTIFY_TOKEN)

    @property
    def smtp_from_email(self) -> str:
        """Visible From address: SMTP_FROM_EMAIL, or the sender login itself."""
        return self.SMTP_FROM_EMAIL or self.SMTP_USER

    @property
    def max_verify(self):
        """TLS verify target for MAX API: explicit bundle, repo CABundle, or True."""
        import os
        if self.MAX_CA_BUNDLE:
            return self.MAX_CA_BUNDLE
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        repo_bundle = os.path.join(backend_dir, "certs", "russian_trusted_ca.pem")
        if os.path.isfile(repo_bundle):
            return repo_bundle
        return True

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

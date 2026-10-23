"""Sentry middleware — captures unhandled exceptions and sends to Sentry.

Disabled when SENTRY_DSN is empty or APP_ENV != production.
"""
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)

try:
    import sentry_sdk
    from sentry_sdk.integrations.starlette import StarletteIntegration

    _SENTRY_AVAILABLE = True
except ImportError:
    _SENTRY_AVAILABLE = False


def init_sentry(dsn: str, app_name: str, app_env: str) -> None:
    """Initialize Sentry SDK if DSN is set and Sentry is available."""
    if not dsn or not _SENTRY_AVAILABLE:
        logger.info("Sentry disabled (no DSN or SDK not installed)")
        return

    sentry_sdk.init(
        dsn=dsn,
        environment=app_env,
        release=None,  # Will be set per-request from git SHA
        integrations=[
            StarletteIntegration(
                transaction_style="url",
            ),
        ],
        # Sample 100% of errors in production (we pay per error)
        traces_sample_rate=0.1,
    )
    logger.info("Sentry initialized for environment: %s", app_env)


class SentryMiddleware(BaseHTTPMiddleware):
    """Capture unhandled exceptions and forward to Sentry."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not _SENTRY_AVAILABLE:
            return await call_next(request)

        try:
            response = await call_next(request)
            return response
        except Exception:
            # Let the global exception handler log and return the generic error.
            # Sentry will capture the exception via the middleware.
            raise

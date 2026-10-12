"""Security response headers (defense in depth, framework layer).

Applied OUTERMOST among user middleware so every response carries them —
including rate-limit 429s and unhandled 500s. CSP is intentionally absent:
a strict policy would break Swagger UI and the Vite dev client; revisit
when the public frontend is served from this backend.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Static hardening headers on every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # HSTS on plaintext localhost would poison the browser cache —
        # production (TLS) only.
        if settings.APP_ENV == "production":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response

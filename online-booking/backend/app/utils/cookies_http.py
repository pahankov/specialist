"""Auth cookie helper — framework layer (moved from modules.auth.router).

Any auth flow (password login, OTP, MAX chat-bot) sets the same split-token
cookies through this single function instead of module->module imports.
"""
from fastapi import Response

from app.config import settings


def set_auth_cookies(
    response: Response, access_token: str, refresh_token_value: str | None
) -> None:
    """Set refresh (httpOnly) + access (readable) cookies on the response."""
    if refresh_token_value:
        response.set_cookie(
            key="refresh_token", value=refresh_token_value,
            httponly=True,
            secure=not settings.DEBUG,
            samesite="lax",
            max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
            path="/",
        )
    response.set_cookie(
        key="access_token", value=access_token,
        httponly=False,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )

"""Pydantic schemas for Yandex ID auth (OAuth 2.0 Authorization Code)."""
from pydantic import BaseModel, Field
from typing import Optional


class YandexStartRequest(BaseModel):
    # Yandex uses a plain Authorization Code flow (no PKCE), so the start
    # call carries no challenge — the backend just mints a signed state.
    pass


class YandexStartResponse(BaseModel):
    # Full Yandex authorize URL (client_id + redirect_uri + signed state
    # baked in) — the frontend just redirects the browser.
    authorize_url: str
    # Signed state also returned so the frontend can stash it (it is echoed
    # back by Yandex and must be posted to /yandex/verify unchanged).
    state: str
    client_id: str
    # Canonical backend redirect_uri (must match the registered one).
    redirect_uri: str


class YandexVerifyRequest(BaseModel):
    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    # 152-FZ consent checkbox from the Yandex login form (offer + policy).
    consent: bool = False


class YandexVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: Optional[bool] = None

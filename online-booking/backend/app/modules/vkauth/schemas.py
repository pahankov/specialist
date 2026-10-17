"""Pydantic schemas for VK ID auth (OAuth 2.0 Authorization Code + PKCE)."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class VkStartRequest(BaseModel):
    # PKCE challenge: BASE64URL(SHA256(code_verifier)), generated on the
    # frontend. The verifier itself never leaves the browser until /vk/verify.
    code_challenge: str = Field(min_length=43, max_length=128)


class VkStartResponse(BaseModel):
    # Full VK authorize URL (client_id + redirect_uri + signed state +
    # code_challenge baked in) — the frontend just redirects the browser.
    authorize_url: str
    # Signed state also returned so the frontend can stash it (it is echoed
    # back by VK and must be posted to /vk/verify unchanged).
    state: str
    client_id: str
    # Canonical backend redirect_uri — the VK widget must use the exact same
    # value at authorize time so the server-side exchange matches it.
    redirect_uri: str


class VkVerifyRequest(BaseModel):
    code: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    state: str = Field(min_length=1)
    # PKCE verifier for the code (kept in the browser between redirect legs).
    code_verifier: str = Field(min_length=43, max_length=128)
    # 152-FZ consent checkbox from the VK login form (offer + privacy policy).
    consent: bool = False


class VkVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: Optional[bool] = None

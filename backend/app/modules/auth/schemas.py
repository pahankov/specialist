"""Pydantic schemas for authentication."""
from pydantic import BaseModel


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str


class TokenRefreshRequest(BaseModel):
    pass  # token comes from cookie

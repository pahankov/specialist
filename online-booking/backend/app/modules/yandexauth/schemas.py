"""Pydantic schemas for Yandex ID auth (OAuth 2.0 Authorization Code)."""
from pydantic import BaseModel, Field, model_validator
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
    # Helper page of the official instant-auth widget (sdk-suggest.js).
    # Empty = the widget is not configured; the frontend falls back to the
    # plain redirect button.
    suggest_redirect_uri: str = ""


class YandexVerifyRequest(BaseModel):
    """Exactly one of the two flows per request:

    - the redirect/callback flow sends `code` + `state`;
    - the official widget flow sends the SDK-delivered `access_token`.
    """

    code: Optional[str] = Field(default=None, min_length=1)
    state: Optional[str] = Field(default=None, min_length=1)
    access_token: Optional[str] = Field(default=None, min_length=1)
    # 152-FZ consent checkbox from the Yandex login form (offer + policy).
    consent: bool = False

    @model_validator(mode="after")
    def _exactly_one_flow(self):
        code_flow = self.code is not None or self.state is not None
        if code_flow and self.access_token is not None:
            raise ValueError(
                "code/state and access_token are mutually exclusive")
        if not code_flow and self.access_token is None:
            raise ValueError("code + state or access_token is required")
        if code_flow and (self.code is None or self.state is None):
            raise ValueError("code and state must be sent together")
        return self


class YandexVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: Optional[bool] = None

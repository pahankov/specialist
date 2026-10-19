"""Pydantic schemas for Yandex ID auth (Authorization Code + widget)."""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Union


class YandexStartRequest(BaseModel):
    # Yandex uses a plain Authorization Code flow (no PKCE), so the start
    # call carries no challenge — the backend just mints a signed state.
    # link=True (authenticated) mints a state that binds the profile to the
    # CURRENT account («Привязать Яндекс») instead of logging in.
    link: bool = False


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


class YandexVerifyCodeRequest(BaseModel):
    """Redirect/callback flow: the code + the signed state echoed by Yandex."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    state: str = Field(min_length=1)
    # 152-FZ consent checkbox from the Yandex login form (offer + policy).
    consent: bool = False


class YandexVerifyTokenRequest(BaseModel):
    """Official widget flow: the SDK-delivered token, checked via user_info."""

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(min_length=1)
    # 152-FZ consent checkbox from the Yandex login form (offer + policy).
    consent: bool = False


# Exactly one flow per request: `extra="forbid"` on both models makes the
# shapes mutually exclusive, so the union itself rejects mixed/empty payloads
# and each flow keeps its strictly typed schema (FastAPI/OpenAPI show both).
YandexVerifyRequest = Union[YandexVerifyCodeRequest, YandexVerifyTokenRequest]


class YandexVerifyResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: Optional[bool] = None
    # Challenge token for the 2-step consent flow (1.80.0). Present only
    # for new accounts without consent — the frontend shows ConsentScreen,
    # then calls /auth/consent/complete with this challenge.
    challenge: Optional[str] = None

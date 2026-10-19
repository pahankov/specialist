"""Yandex ID OAuth 2.0 client (https://oauth.yandex.ru).

Authorization Code Flow with a SERVER-SIDE code exchange — unlike VK there is
no PKCE; the exchange uses the app's OAuth secret (`client_secret`), which
never leaves the backend, so the access token never touches the browser.
Two calls:

- exchange_code(): POST https://oauth.yandex.ru/token
  grant_type=authorization_code + code + client_id + client_secret
  -> { access_token, expires_in, token_type }.
- user_info():    GET  https://login.yandex.ru/info?format=json
  with header `Authorization: OAuth <token>`
  -> { id, login, first_name, last_name, default_email, ... }.

Both are JSON (the token call is form-encoded, the info call is a GET). The
flow orchestration (user create/bind, JWT session) lives in
app.modules.yandexauth.service — this module only talks HTTP.
"""
import logging
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

TOKEN_URL = "https://oauth.yandex.ru/token"
INFO_URL = "https://login.yandex.ru/info"


class YandexApiError(Exception):
    """Yandex returned an error payload or was unreachable."""


class YandexAuthApi:
    """Minimal async client: exchange_code / user_info."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        redirect_uri: str = "",
        timeout: float = 15.0,
    ):
        self._client_id = client_id or settings.YANDEX_CLIENT_ID
        self._client_secret = client_secret or settings.YANDEX_CLIENT_SECRET
        self._redirect_uri = redirect_uri or settings.YANDEX_REDIRECT_URI
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(
            self._client_id and self._client_secret and self._redirect_uri)

    async def exchange_code(self, code: str) -> dict:
        """Trade the authorization code for an access token (server-side)."""
        if not self.enabled:
            raise YandexApiError("Yandex ID is not configured")
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "client_id": self._client_id,
            "client_secret": self._client_secret,
        }
        # redirect_uri is optional for Yandex but echo it when known so the
        # exchange matches the authorize request exactly.
        if self._redirect_uri:
            data["redirect_uri"] = self._redirect_uri
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(TOKEN_URL, data=data)
        except Exception as e:
            raise YandexApiError(f"Yandex ID unreachable: {e}")
        return self._parse(resp, "token")

    async def user_info(self, access_token: str) -> dict:
        """Return the profile block for a fresh access token."""
        if not self.enabled:
            raise YandexApiError("Yandex ID is not configured")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    INFO_URL,
                    params={"format": "json"},
                    headers={"Authorization": f"OAuth {access_token}"},
                )
        except Exception as e:
            raise YandexApiError(f"Yandex ID unreachable: {e}")
        return self._parse(resp, "info")

    async def token_client_id(self, access_token: str) -> str:
        """Client id of the app this OAuth token was issued to ("" if none).

        The widget («мгновенная авторизация») hands the site a raw token:
        it must belong to THIS app — a token minted for another client_id
        must never log anyone into our site.

        Read from login.yandex.ru/info with the Authorization header: the
        oauth.yandex.ru/info alias answers widget tokens with a non-JSON
        body, which parsed as client_id="" and 401'd every instant-auth
        login (real tokens carry the id — verified 2026-10-19).
        """
        if not self.enabled:
            raise YandexApiError("Yandex ID is not configured")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    INFO_URL,
                    params={"format": "json"},
                    headers={"Authorization": f"OAuth {access_token}"},
                )
        except Exception as e:
            raise YandexApiError(f"Yandex ID unreachable: {e}")
        payload = self._parse(resp, "token-info")
        client_id = payload.get("client_id")
        return str(client_id) if client_id else ""

    @staticmethod
    def _parse(resp: httpx.Response, where: str) -> dict:
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        # Yandex reports auth failures in the body (error + error_description)
        # and may still use a 200 status — check the body first.
        if isinstance(payload, dict) and payload.get("error"):
            desc = payload.get("error_description") or payload.get("error")
            raise YandexApiError(f"Yandex {where} error: {desc}")
        if resp.status_code >= 400:
            raise YandexApiError(
                f"Yandex {where} {resp.status_code}: {resp.text[:200]}")
        if not isinstance(payload, dict):
            raise YandexApiError(f"Yandex {where}: unexpected response shape")
        return payload


def get_yandex_api(
    client_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> YandexAuthApi:
    return YandexAuthApi(
        client_id=client_id or "",
        client_secret=client_secret or "",
        redirect_uri=redirect_uri or "",
    )

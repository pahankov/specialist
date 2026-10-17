"""VK ID OAuth 2.0 client (https://id.vk.ru, docs: dev.vk.ru).

Authorization Code Flow + PKCE with a SERVER-SIDE code exchange (the
recommended scheme for apps with a backend — the tokens never touch the
browser). Only two calls are needed:

- exchange_code(): POST /oauth2/auth  grant_type=authorization_code ->
  access_token + refresh_token + id_token + user_id.
- user_info():    POST /oauth2/user_info  access_token -> profile fields.

Both are form-encoded (VK rejects JSON bodies for these endpoints). Outbound
calls reuse httpx (already a dependency). The flow orchestration (user
create/bind, JWT session) lives in app.modules.vkauth.service — this module
only talks HTTP.
"""
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://id.vk.ru"


class VkApiError(Exception):
    """VK ID returned an error payload or was unreachable."""


class VkAuthApi:
    """Minimal async client: exchange_code / user_info."""

    def __init__(
        self,
        client_id: str = "",
        service_token: str = "",
        redirect_uri: str = "",
        timeout: float = 15.0,
    ):
        self._client_id = client_id or settings.VK_CLIENT_ID
        self._service_token = service_token or settings.VK_SERVICE_TOKEN
        self._redirect_uri = redirect_uri or settings.VK_REDIRECT_URI
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self._client_id and self._redirect_uri)

    async def _post_form(self, path: str, data: dict) -> dict:
        url = f"{BASE_URL}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(url, data=data)
        except Exception as e:
            raise VkApiError(f"VK ID unreachable: {e}")
        try:
            payload = resp.json()
        except Exception:
            payload = {}
        # VK reports auth failures in the body (error + error_description)
        # and may still use a 200 status — check the body first.
        if isinstance(payload, dict) and payload.get("error"):
            desc = payload.get("error_description") or payload.get("error")
            raise VkApiError(f"VK ID {path} error: {desc}")
        if resp.status_code >= 400:
            raise VkApiError(
                f"VK ID {path} {resp.status_code}: {resp.text[:200]}")
        if not isinstance(payload, dict):
            raise VkApiError(f"VK ID {path}: unexpected response shape")
        return payload

    async def exchange_code(
        self, code: str, code_verifier: str, device_id: str, state: str
    ) -> dict:
        """Trade the authorization code for tokens (PKCE-verified server-side)."""
        if not self.enabled:
            raise VkApiError("VK ID is not configured")
        data = {
            "grant_type": "authorization_code",
            "client_id": self._client_id,
            "code": code,
            "code_verifier": code_verifier,
            "redirect_uri": self._redirect_uri,
            "device_id": device_id,
            "state": state,
        }
        # Confidential apps must additionally prove app ownership. VK ID docs
        # call this the OAuth `client_secret`; older VK API flows call it the
        # «Сервисный ключ доступа» (`service_token`). Send BOTH names with the
        # same configured secret so the exchange works whichever VK expects
        # (VK ignores unknown params).
        if self._service_token:
            data["client_secret"] = self._service_token
            data["service_token"] = self._service_token
        return await self._post_form("/oauth2/auth", data)

    async def user_info(self, access_token: str) -> dict:
        """Return the profile block (user.*) for a fresh access token."""
        if not self.enabled:
            raise VkApiError("VK ID is not configured")
        return await self._post_form(
            "/oauth2/user_info",
            {"client_id": self._client_id, "access_token": access_token},
        )


def get_vk_api(
    client_id: Optional[str] = None,
    service_token: Optional[str] = None,
    redirect_uri: Optional[str] = None,
) -> VkAuthApi:
    return VkAuthApi(
        client_id=client_id or "",
        service_token=service_token or "",
        redirect_uri=redirect_uri or "",
    )

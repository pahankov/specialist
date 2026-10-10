"""MAX messenger Bot API client (https://dev.max.ru/docs-api).

Base: https://platform-api2.max.ru, token via `Authorization` header
(query-param tokens are rejected by MAX). Outbound calls only need httpx
(already a dependency). Update intake (webhook/long-poll) is parsed by
app.modules.maxauth.service.parse_update — this module only talks HTTP.
"""
import logging
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://platform-api2.max.ru"


class MaxApiError(Exception):
    """MAX API returned non-2xx or unreachable."""


class MaxBotApi:
    """Minimal async client: me / send_message / updates / subscriptions."""

    def __init__(self, token: str = "", timeout: float = 15.0):
        self._token = token or settings.MAX_BOT_TOKEN
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self._token)

    def _headers(self) -> dict:
        return {"Authorization": self._token, "Content-Type": "application/json"}

    async def _request(self, method: str, path: str, **kwargs) -> Any:
        if not self.enabled:
            raise MaxApiError("MAX_BOT_TOKEN is not configured")
        url = f"{BASE_URL}{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, verify=settings.max_verify
            ) as client:
                resp = await client.request(method, url, headers=self._headers(), **kwargs)
        except Exception as e:
            raise MaxApiError(f"MAX API unreachable: {e}")
        if resp.status_code == 401:
            raise MaxApiError("MAX API 401: invalid bot token")
        if resp.status_code == 429:
            raise MaxApiError("MAX API 429: rate limited")
        if resp.status_code >= 400:
            raise MaxApiError(f"MAX API {resp.status_code}: {resp.text[:200]}")
        try:
            return resp.json()
        except Exception:
            return {}

    async def get_me(self) -> dict:
        """Verify token and return bot info (BotInfo)."""
        return await self._request("GET", "/me")

    async def send_message(self, user_id: int, text: str) -> dict:
        """Send a plain-text message to a dialog (<=2 msg/sec per dialog)."""
        return await self._request(
            "POST", "/messages", params={"user_id": user_id},
            json={"text": text[:4000]},
        )

    async def get_updates(
        self,
        marker: Optional[int] = None,
        timeout: int = 30,
        limit: int = 100,
        types: str = "message_created,bot_started",
    ) -> dict:
        """Long-poll updates — dev/test only, production uses webhook."""
        params: dict = {"timeout": timeout, "limit": limit, "types": types}
        if marker is not None:
            params["marker"] = marker
        return await self._request("GET", "/updates", params=params)

    async def set_webhook(self, url: str, secret: str) -> dict:
        """Subscribe production updates (HTTPS :443, trusted CA cert required)."""
        return await self._request(
            "POST", "/subscriptions",
            json={"url": url,
                  "update_types": ["message_created", "bot_started"],
                  "secret": secret},
        )

    async def delete_webhook(self) -> dict:
        return await self._request("DELETE", "/subscriptions")

    async def get_subscriptions(self) -> dict:
        return await self._request("GET", "/subscriptions")


def get_max_api() -> MaxBotApi:
    return MaxBotApi()

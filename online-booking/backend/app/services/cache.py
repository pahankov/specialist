"""Redis caching service for dashboard statistics.

Async-first (``redis.asyncio`` — never blocks the event loop), fail-open
(graceful degradation when Redis is unavailable), ``v1:`` key namespace,
non-blocking ``SCAN`` for pattern invalidation instead of ``KEYS``.
"""
import json
import logging
from typing import Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

KEY_PREFIX = "v1:"


class CacheService:
    """Async Redis-based cache with TTL support."""

    def __init__(self):
        self._redis = None
        self._enabled: Optional[bool] = None  # None = not probed yet (lazy)

    def _key(self, key: str) -> str:
        return key if key.startswith(KEY_PREFIX) else f"{KEY_PREFIX}{key}"

    async def _client(self):
        """Lazy async Redis client (probed once, then cached or disabled)."""
        if self._redis is not None:
            return self._redis
        if self._enabled is False:
            return None
        try:
            from redis import asyncio as redis_async
            client = redis_async.from_url(
                settings.REDIS_URL, decode_responses=True, socket_connect_timeout=2
            )
            await client.ping()
            self._redis = client
            self._enabled = True
            logger.info("Redis cache connected: %s", settings.REDIS_URL)
            return client
        except Exception as e:
            logger.warning("Redis not available, cache disabled: %s", e)
            self._enabled = False
            self._redis = None
            return None

    @property
    def enabled(self) -> bool:
        return self._enabled is True

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        client = await self._client()
        if client is None:
            return None
        try:
            raw = await client.get(self._key(key))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.debug("Cache GET error: %s", e)
            return None

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL (default 5 minutes)."""
        client = await self._client()
        if client is None:
            return
        try:
            await client.setex(self._key(key), ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.debug("Cache SET error: %s", e)

    async def delete(self, key: str) -> None:
        """Delete value from cache."""
        client = await self._client()
        if client is None:
            return
        try:
            await client.delete(self._key(key))
        except Exception as e:
            logger.debug("Cache DELETE error: %s", e)

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching pattern (non-blocking SCAN)."""
        client = await self._client()
        if client is None:
            return
        try:
            full_pattern = self._key(pattern)
            keys: list[str] = []
            async for key in client.scan_iter(match=full_pattern, count=200):
                keys.append(key)
            if keys:
                await client.delete(*keys)
        except Exception as e:
            logger.debug("Cache invalidate error: %s", e)

    async def health_check(self) -> dict:
        """Check Redis connectivity."""
        client = await self._client()
        if client is None:
            return {"cache": "disabled", "detail": "Redis not available"}
        try:
            await client.ping()
            info = await client.info("memory")
            return {
                "cache": "connected",
                "used_memory_human": info.get("used_memory_human", "N/A"),
            }
        except Exception as e:
            return {"cache": "error", "detail": str(e)}


# Singleton instance
cache_service = CacheService()

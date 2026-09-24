"""Redis caching service for dashboard statistics."""
import json
import logging
from typing import Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class CacheService:
    """Simple Redis-based cache with TTL support."""

    def __init__(self):
        self._redis = None
        self._enabled = False
        self._try_connect()

    def _try_connect(self):
        """Try to connect to Redis, disable cache if unavailable."""
        try:
            import redis
            redis_url = settings.get("REDIS_URL", "redis://localhost:6379/0")
            self._redis = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=2)
            self._redis.ping()
            self._enabled = True
            logger.info("Redis cache connected: %s", redis_url)
        except Exception as e:
            logger.warning("Redis not available, cache disabled: %s", e)
            self._enabled = False
            self._redis = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        if not self._enabled:
            return None
        try:
            raw = self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.debug("Cache GET error: %s", e)
            return None

    def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache with TTL (default 5 minutes)."""
        if not self._enabled:
            return
        try:
            self._redis.setex(key, ttl, json.dumps(value, default=str))
        except Exception as e:
            logger.debug("Cache SET error: %s", e)

    def delete(self, key: str) -> None:
        """Delete value from cache."""
        if not self._enabled:
            return
        try:
            self._redis.delete(key)
        except Exception as e:
            logger.debug("Cache DELETE error: %s", e)

    def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all keys matching pattern."""
        if not self._enabled:
            return
        try:
            keys = self._redis.keys(pattern)
            if keys:
                self._redis.delete(*keys)
        except Exception as e:
            logger.debug("Cache invalidate error: %s", e)

    def health_check(self) -> dict:
        """Check Redis connectivity."""
        if not self._enabled:
            return {"cache": "disabled", "detail": "Redis not available"}
        try:
            self._redis.ping()
            info = self._redis.info("memory")
            return {
                "cache": "connected",
                "used_memory_human": info.get("used_memory_human", "N/A"),
            }
        except Exception as e:
            return {"cache": "error", "detail": str(e)}


# Singleton instance
cache_service = CacheService()

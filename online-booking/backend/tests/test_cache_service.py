"""Tests for cache service (Redis + fallback).

Covers:
- CacheService.get / set / delete
- Fallback behavior when Redis is unavailable
- Health check
- TTL support
"""
import pytest
from unittest.mock import MagicMock, patch
import json as json_module


# ─── CacheService with disabled Redis (fallback) ─────────────────────


class TestCacheServiceFallback:
    """Tests for CacheService when Redis is unavailable."""

    def _make_disabled_service(self):
        """Create a CacheService with mocked Redis that fails."""
        import sys
        from unittest.mock import MagicMock

        # Remove cached modules to force reimport
        for key in list(sys.modules.keys()):
            if key.startswith("app.services.cache"):
                del sys.modules[key]

        # Mock redis module to raise on connection
        mock_redis_mod = MagicMock()
        mock_redis_mod.from_url.side_effect = Exception("Connection refused")
        sys.modules["redis"] = mock_redis_mod

        from app.services.cache import CacheService
        service = CacheService()
        return service, mock_redis_mod

    def test_cache_disabled_when_redis_unavailable(self):
        """Cache is disabled when Redis connection fails."""
        service, _ = self._make_disabled_service()
        assert service.enabled is False

    def test_get_returns_none_when_disabled(self):
        """get() returns None when cache is disabled."""
        service, _ = self._make_disabled_service()
        assert service.get("any_key") is None

    def test_set_does_nothing_when_disabled(self):
        """set() does nothing when cache is disabled."""
        service, _ = self._make_disabled_service()
        # Should not raise
        service.set("any_key", {"data": "value"})

    def test_delete_does_nothing_when_disabled(self):
        """delete() does nothing when cache is disabled."""
        service, _ = self._make_disabled_service()
        # Should not raise
        service.delete("any_key")

    def test_health_check_returns_disabled(self):
        """health_check() returns disabled status when Redis is unavailable."""
        service, _ = self._make_disabled_service()
        result = service.health_check()
        assert result["cache"] == "disabled"
        assert "Redis not available" in result["detail"]


# ─── CacheService with mocked Redis ──────────────────────────────────


class TestCacheService:
    """Tests for CacheService with mocked Redis."""

    @pytest.fixture
    def mock_cache_service(self):
        """Create a CacheService with mocked Redis."""
        from app.services.cache import CacheService

        service = CacheService.__new__(CacheService)
        service._redis = MagicMock()
        service._enabled = True
        return service

    async def test_cache_set_get(self, mock_cache_service):
        """set() and get() work correctly."""
        import json

        mock_cache_service._redis.get.return_value = json.dumps({"key": "value"})

        result = mock_cache_service.get("test_key")
        assert result == {"key": "value"}

        mock_cache_service._redis.get.assert_called_once_with("test_key")

    async def test_cache_delete(self, mock_cache_service):
        """delete() calls Redis delete."""
        mock_cache_service.delete("test_key")
        mock_cache_service._redis.delete.assert_called_once_with("test_key")

    async def test_cache_get_missing(self, mock_cache_service):
        """get() returns None for missing key."""
        mock_cache_service._redis.get.return_value = None

        result = mock_cache_service.get("missing_key")
        assert result is None

    async def test_cache_set_with_ttl(self, mock_cache_service):
        """set() uses setex with TTL."""
        import json

        mock_cache_service.set("test_key", {"data": "value"}, ttl=600)

        # setex(key, ttl, value) should be called
        mock_cache_service._redis.setex.assert_called_once()
        call_args = mock_cache_service._redis.setex.call_args
        assert call_args[0][0] == "test_key"
        assert call_args[0][1] == 600  # TTL

    async def test_cache_health_check_connected(self, mock_cache_service):
        """health_check() returns connected status when Redis is available."""
        mock_cache_service._redis.ping.return_value = True
        mock_cache_service._redis.info.return_value = {"used_memory_human": "1.5MB"}

        result = mock_cache_service.health_check()
        assert result["cache"] == "connected"
        assert result["used_memory_human"] == "1.5MB"

    async def test_cache_invalidate_pattern(self, mock_cache_service):
        """invalidate_pattern() deletes all matching keys."""
        mock_cache_service._redis.keys.return_value = ["key1", "key2", "key3"]

        mock_cache_service.invalidate_pattern("test:*")

        mock_cache_service._redis.keys.assert_called_once_with("test:*")
        mock_cache_service._redis.delete.assert_called_once_with("key1", "key2", "key3")

    async def test_cache_invalidate_pattern_no_keys(self, mock_cache_service):
        """invalidate_pattern() does nothing when no keys match."""
        mock_cache_service._redis.keys.return_value = []

        mock_cache_service.invalidate_pattern("test:*")

        mock_cache_service._redis.keys.assert_called_once_with("test:*")
        mock_cache_service._redis.delete.assert_not_called()

    async def test_cache_get_decodes_json(self, mock_cache_service):
        """get() correctly decodes JSON values."""
        import json

        mock_cache_service._redis.get.return_value = json.dumps([1, 2, 3])

        result = mock_cache_service.get("list_key")
        assert result == [1, 2, 3]

    async def test_cache_set_encodes_json(self, mock_cache_service):
        """set() correctly encodes values to JSON."""
        mock_cache_service.set("list_key", [1, 2, 3])

        call_args = mock_cache_service._redis.setex.call_args
        value = call_args[0][2]
        assert json_module.loads(value) == [1, 2, 3]

    async def test_cache_get_handles_decode_error(self, mock_cache_service):
        """get() returns None on JSON decode error."""
        import json

        mock_cache_service._redis.get.return_value = "not valid json {{{"

        result = mock_cache_service.get("bad_key")
        assert result is None

    async def test_cache_set_handles_error(self, mock_cache_service):
        """set() doesn't raise on Redis error."""
        mock_cache_service._redis.setex.side_effect = Exception("Redis error")

        # Should not raise
        mock_cache_service.set("test_key", {"data": "value"})


# ─── Singleton instance ──────────────────────────────────────────────


class TestCacheServiceSingleton:
    """Tests for the cache_service singleton."""

    def test_singleton_exists(self):
        """cache_service singleton is accessible."""
        from app.services.cache import cache_service
        assert cache_service is not None

    def test_singleton_has_enabled_property(self):
        """cache_service has enabled property."""
        from app.services.cache import cache_service
        assert hasattr(cache_service, "enabled")
        assert isinstance(cache_service.enabled, bool)

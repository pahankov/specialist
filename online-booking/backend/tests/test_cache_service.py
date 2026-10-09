"""Tests for async cache service (redis.asyncio + fail-open fallback).

Covers:
- CacheService.get / set / delete (async)
- Fallback behavior when Redis is unavailable
- Health check
- TTL support + v1: key namespace + SCAN invalidation
"""
import json as json_module
import pytest
from unittest.mock import AsyncMock


def _make_disabled_service():
    """Create a CacheService whose lazy connect always fails (probed + disabled)."""
    from app.services.cache import CacheService

    service = CacheService()

    async def _no_client():
        service._enabled = False
        return None
    service._client = _no_client  # type: ignore[method-assign]
    return service


def _make_mocked_service():
    """Create a CacheService with an AsyncMock Redis client (already connected)."""
    from app.services.cache import CacheService, KEY_PREFIX

    service = CacheService()
    client = AsyncMock()
    service._redis = client
    service._enabled = True

    async def _client():
        return client
    service._client = _client  # type: ignore[method-assign]
    return service, client, KEY_PREFIX


class TestCacheServiceFallback:
    """Tests for CacheService when Redis is unavailable."""

    async def test_cache_disabled_when_redis_unavailable(self):
        service = _make_disabled_service()
        assert await service._client() is None
        assert service.enabled is False

    async def test_get_returns_none_when_disabled(self):
        service = _make_disabled_service()
        assert await service.get("any_key") is None

    async def test_set_does_nothing_when_disabled(self):
        service = _make_disabled_service()
        await service.set("any_key", {"data": "value"})  # should not raise

    async def test_delete_does_nothing_when_disabled(self):
        service = _make_disabled_service()
        await service.delete("any_key")  # should not raise

    async def test_health_check_returns_disabled(self):
        service = _make_disabled_service()
        result = await service.health_check()
        assert result["cache"] == "disabled"
        assert "Redis not available" in result["detail"]

    async def test_invalidate_does_nothing_when_disabled(self):
        service = _make_disabled_service()
        await service.invalidate_pattern("test:*")  # should not raise


class TestCacheService:
    """Tests for CacheService with mocked async Redis."""

    async def test_cache_set_get(self):
        import json

        service, client, _ = _make_mocked_service()
        client.get.return_value = json.dumps({"key": "value"})

        result = await service.get("test_key")
        assert result == {"key": "value"}
        client.get.assert_awaited_once_with("v1:test_key")

    async def test_cache_delete(self):
        service, client, _ = _make_mocked_service()
        await service.delete("test_key")
        client.delete.assert_awaited_once_with("v1:test_key")

    async def test_cache_get_missing(self):
        service, client, _ = _make_mocked_service()
        client.get.return_value = None

        result = await service.get("missing_key")
        assert result is None

    async def test_cache_set_with_ttl(self):
        service, client, _ = _make_mocked_service()
        await service.set("test_key", {"data": "value"}, ttl=600)

        client.setex.assert_awaited_once()
        call_args = client.setex.call_args
        assert call_args[0][0] == "v1:test_key"
        assert call_args[0][1] == 600  # TTL

    async def test_cache_health_check_connected(self):
        service, client, _ = _make_mocked_service()
        client.ping.return_value = True
        client.info.return_value = {"used_memory_human": "1.5MB"}

        result = await service.health_check()
        assert result["cache"] == "connected"
        assert result["used_memory_human"] == "1.5MB"

    async def test_cache_invalidate_pattern(self):
        """invalidate_pattern() SCANs and deletes all matching keys."""
        service, client, _ = _make_mocked_service()

        async def _scan_iter(match=None, count=None):
            for k in ("v1:key1", "v1:key2", "v1:key3"):
                yield k

        client.scan_iter = _scan_iter
        await service.invalidate_pattern("test:*")

        client.delete.assert_awaited_once_with("v1:key1", "v1:key2", "v1:key3")

    async def test_cache_invalidate_pattern_no_keys(self):
        service, client, _ = _make_mocked_service()

        async def _scan_iter(match=None, count=None):
            return
            yield  # make it an async generator

        client.scan_iter = _scan_iter
        await service.invalidate_pattern("test:*")

        client.delete.assert_not_awaited()

    async def test_cache_get_decodes_json(self):
        import json

        service, client, _ = _make_mocked_service()
        client.get.return_value = json.dumps([1, 2, 3])

        result = await service.get("list_key")
        assert result == [1, 2, 3]

    async def test_cache_set_encodes_json(self):
        service, client, _ = _make_mocked_service()
        await service.set("list_key", [1, 2, 3])

        call_args = client.setex.call_args
        value = call_args[0][2]
        assert json_module.loads(value) == [1, 2, 3]

    async def test_cache_get_handles_decode_error(self):
        service, client, _ = _make_mocked_service()
        client.get.return_value = "not valid json {{{"

        result = await service.get("bad_key")
        assert result is None

    async def test_cache_set_handles_error(self):
        service, client, _ = _make_mocked_service()
        client.setex.side_effect = Exception("Redis error")

        await service.set("test_key", {"data": "value"})  # should not raise


class TestCacheServiceSingleton:
    """Tests for the cache_service singleton."""

    def test_singleton_exists(self):
        from app.services.cache import cache_service
        assert cache_service is not None

    def test_singleton_has_enabled_property(self):
        from app.services.cache import cache_service
        assert hasattr(cache_service, "enabled")
        assert isinstance(cache_service.enabled, bool)

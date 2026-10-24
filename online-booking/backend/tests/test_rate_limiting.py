"""Tests for slowapi rate limiting.

Replaces old in-memory RateLimiter tests with slowapi-compatible tests.
slowapi uses decorators (@limiter.limit) instead of manual is_allowed() calls.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.config import settings
from app.main import app
from app.middleware.rate_limit import _storage_uri, limiter


@pytest.fixture
def client():
    """Create test client with rate limiting enabled."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestRateLimitMiddleware:
    """Tests for rate limiting HTTP behavior with slowapi."""

    async def test_health_endpoint_skips_rate_limit(self, client):
        """Health check endpoint is not rate limited."""
        for _ in range(100):
            resp = await client.get("/health")
            assert resp.status_code == 200

    async def test_docs_endpoint_skips_rate_limit(self, client):
        """Docs endpoint is not rate limited."""
        for _ in range(100):
            resp = await client.get("/docs")
            assert resp.status_code == 200

    async def test_limiter_is_configured(self):
        """Verify slowapi limiter is properly configured."""
        assert limiter is not None

    def test_storage_uri_memory_in_development(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "development")
        monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", "")
        assert _storage_uri() == "memory://"

    def test_storage_uri_redis_in_production(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "production")
        monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", "")
        monkeypatch.setattr(settings, "REDIS_URL", "redis://redis:6379/2")
        assert _storage_uri() == "redis://redis:6379/2"

    def test_storage_uri_explicit_override(self, monkeypatch):
        monkeypatch.setattr(settings, "APP_ENV", "development")
        monkeypatch.setattr(settings, "RATE_LIMIT_STORAGE_URI", "redis://custom:6379/3")
        assert _storage_uri() == "redis://custom:6379/3"

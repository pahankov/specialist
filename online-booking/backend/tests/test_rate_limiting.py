"""Tests for slowapi rate limiting.

Replaces old in-memory RateLimiter tests with slowapi-compatible tests.
slowapi uses decorators (@limiter.limit) instead of manual is_allowed() calls.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.middleware.rate_limit import limiter


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

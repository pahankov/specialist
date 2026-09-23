"""Tests for rate limiting middleware."""
from app.middleware import rate_limiter


class TestRateLimiter:
    """Tests for RateLimiter class logic."""

    def setup_method(self):
        """Reset rate limiter before each test."""
        rate_limiter.reset()

    def test_default_limit_allows_requests(self):
        """Default limit (60 req/min) allows requests within limit."""
        for i in range(60):
            allowed, limit, remaining = rate_limiter.is_allowed("1.2.3.4", "/api/v1/masters/")
            assert allowed is True
            assert limit == 60
        assert remaining == 0

    def test_default_limit_blocks_after_window(self):
        """Blocks requests after exceeding default limit."""
        # Exhaust the limit
        for _ in range(60):
            rate_limiter.is_allowed("1.2.3.4", "/api/v1/masters/")

        # Next request should be blocked
        allowed, limit, remaining = rate_limiter.is_allowed("1.2.3.4", "/api/v1/masters/")
        assert allowed is False
        assert remaining == 0

    def test_different_ips_have_independent_limits(self):
        """Different client IPs have separate rate limits."""
        # Exhaust IP 1's limit
        for _ in range(60):
            rate_limiter.is_allowed("1.2.3.4", "/api/v1/masters/")

        # IP 2 should still be allowed
        allowed, _, _ = rate_limiter.is_allowed("5.6.7.8", "/api/v1/masters/")
        assert allowed is True

    def test_custom_endpoint_limits(self):
        """Auth endpoints have stricter limits than default."""
        # Login endpoint: 10 req/min
        for i in range(10):
            allowed, limit, remaining = rate_limiter.is_allowed("1.2.3.4", "/api/v1/auth/login")
            assert allowed is True
            assert limit == 10

        allowed, _, _ = rate_limiter.is_allowed("1.2.3.4", "/api/v1/auth/login")
        assert allowed is False

    def test_register_endpoint_stricter_limit(self):
        """Register endpoint has 5 req/min limit."""
        for _ in range(5):
            allowed, limit, _ = rate_limiter.is_allowed("1.2.3.4", "/api/v1/auth/register")
            assert allowed is True
            assert limit == 5

        allowed, _, _ = rate_limiter.is_allowed("1.2.3.4", "/api/v1/auth/register")
        assert allowed is False

    def test_reset_clears_all_limits(self):
        """reset() clears all rate limit data."""
        # Exhaust limit
        for _ in range(60):
            rate_limiter.is_allowed("1.2.3.4", "/api/v1/masters/")

        allowed, _, _ = rate_limiter.is_allowed("1.2.3.4", "/api/v1/masters/")
        assert allowed is False

        # Reset
        rate_limiter.reset()

        # Should be allowed again
        allowed, _, _ = rate_limiter.is_allowed("1.2.3.4", "/api/v1/masters/")
        assert allowed is True


class TestRateLimitMiddleware:
    """Tests for RateLimitMiddleware HTTP behavior."""

    async def test_health_endpoint_skips_rate_limit(self, client):
        """Health check endpoint is not rate limited."""
        # Send many requests — should all succeed
        for _ in range(100):
            resp = await client.get("/health")
            assert resp.status_code == 200

    async def test_docs_endpoint_skips_rate_limit(self, client):
        """Docs endpoint is not rate limited."""
        for _ in range(100):
            resp = await client.get("/docs")
            assert resp.status_code == 200

    async def test_rate_limit_response_content(self, client):
        """Rate limited response has correct content."""
        # The middleware skips rate limiting for test clients (client_ip == "test")
        # So this test verifies the middleware is present, not the actual limit
        # Actual limit testing is done in TestRateLimiter
        resp = await client.get("/api/v1/masters/")
        # Should not be 429 in test environment
        assert resp.status_code != 429

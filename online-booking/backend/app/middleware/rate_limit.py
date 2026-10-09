"""slowapi rate limiter configuration for FastAPI.

Replaces the old in-memory RateLimiter with slowapi — a production-ready
rate limiter that supports Redis-backed storage for horizontal scaling.

Migration: 2026-10-02
- Old: self-written RateLimiter in app/middleware/rate_limit.py (in-memory only)
- New: slowapi with memory storage (falls back to memory if Redis unavailable)
"""
import asyncio
import os
from functools import wraps
from slowapi import Limiter
from slowapi.util import get_remote_address


class _NoOpLimiter:
    """No-op limiter that always allows — used in test environments."""
    def limit(self, limit_str):
        def decorator(fn):
            if asyncio.iscoroutinefunction(fn):
                @wraps(fn)
                async def async_wrapper(*args, **kwargs):
                    return await fn(*args, **kwargs)
                return async_wrapper

            @wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    def exempt(self, fn):
        """No-op exempt — returns function unchanged (mirrors slowapi API)."""
        return fn


# Disable rate limiting in test environments to avoid 429 errors
# Set RATE_LIMIT_DISABLED=true in CI/test environment
if os.getenv("RATE_LIMIT_DISABLED") == "true":
    limiter = _NoOpLimiter()
else:
    # Global default: 60 req/min everywhere; auth endpoints override to 10/min
    # via @limiter.limit("10/minute") on router handlers.
    limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])


def wire_rate_limit(app):
    """Attach slowapi limiter to FastAPI app (state + handler + middleware).

    No-op in test env (_NoOpLimiter has no state to wire).
    Must be called AFTER app creation, BEFORE include_router is irrelevant
    (middleware applies globally either way).
    """
    if isinstance(limiter, _NoOpLimiter):
        return
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware
    from fastapi.responses import JSONResponse

    app.state.limiter = limiter

    async def _rate_limit_handler(request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Слишком много запросов. Попробуйте позже."},
        )

    app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

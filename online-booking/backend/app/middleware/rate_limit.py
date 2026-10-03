"""slowapi rate limiter configuration for FastAPI.

Replaces the old in-memory RateLimiter with slowapi — a production-ready
rate limiter that supports Redis-backed storage for horizontal scaling.

Migration: 2026-10-02
- Old: self-written RateLimiter in app/middleware/rate_limit.py (in-memory only)
- New: slowapi with memory storage (falls back to memory if Redis unavailable)
"""
import os
from functools import wraps
from slowapi import Limiter
from slowapi.util import get_remote_address


class _NoOpLimiter:
    """No-op limiter that always allows — used in test environments."""
    def limit(self, limit_str):
        def decorator(fn):
            @wraps(fn)
            def wrapper(*args, **kwargs):
                return fn(*args, **kwargs)
            return wrapper
        return decorator


# Disable rate limiting in test environments to avoid 429 errors
# Set RATE_LIMIT_DISABLED=true in CI/test environment
if os.getenv("RATE_LIMIT_DISABLED") == "true":
    limiter = _NoOpLimiter()
else:
    limiter = Limiter(key_func=get_remote_address, default_limits=[])

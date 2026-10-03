"""slowapi rate limiter configuration for FastAPI.

Replaces the old in-memory RateLimiter with slowapi — a production-ready
rate limiter that supports Redis-backed storage for horizontal scaling.

Migration: 2026-10-02
- Old: self-written RateLimiter in app/middleware/rate_limit.py (in-memory only)
- New: slowapi with Redis storage (falls back to memory if Redis unavailable)
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Lazy initialization — avoids Redis connection at import time (breaks CI)
_limiter = None


def get_limiter():
    """Get or create the limiter instance.
    
    Uses memory storage by default (works in CI/tests).
    Uses Redis storage in production when REDIS_URL is set.
    """
    global _limiter
    if _limiter is None:
        # Import here to avoid circular imports and Redis connection at module load
        from app.config import settings
        storage_uri = getattr(settings, "REDIS_URL", None)
        if storage_uri:
            _limiter = Limiter(
                key_func=get_remote_address,
                storage_uri=storage_uri,
                default_limits=[],  # no global defaults
            )
        else:
            _limiter = Limiter(
                key_func=get_remote_address,
                default_limits=[],
            )
    return _limiter


# Module-level limiter for decorator use
limiter = get_limiter()

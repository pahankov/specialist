"""slowapi rate limiter configuration for FastAPI.

Replaces the old in-memory RateLimiter with slowapi — a production-ready
rate limiter that supports Redis-backed storage for horizontal scaling.

Migration: 2026-10-02
- Old: self-written RateLimiter in app/middleware/rate_limit.py (in-memory only)
- New: slowapi with Redis storage (falls back to memory if Redis unavailable)
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

# Redis storage if available, memory fallback
storage_uri = getattr(settings, "REDIS_URL", None)
if storage_uri:
    limiter = Limiter(key_func=get_remote_address, storage_uri=storage_uri)
else:
    limiter = Limiter(key_func=get_remote_address)

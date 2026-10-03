"""slowapi rate limiter configuration for FastAPI.

Replaces the old in-memory RateLimiter with slowapi — a production-ready
rate limiter that supports Redis-backed storage for horizontal scaling.

Migration: 2026-10-02
- Old: self-written RateLimiter in app/middleware/rate_limit.py (in-memory only)
- New: slowapi with memory storage (falls back to memory if Redis unavailable)
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

# Always use memory storage — Redis connection at request time causes 500 errors
# when Redis is unavailable (CI, dev, or Redis downtime)
# Redis-backed storage can be enabled manually in production if needed
limiter = Limiter(key_func=get_remote_address, default_limits=[])

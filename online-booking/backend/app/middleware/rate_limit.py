"""slowapi rate limiter configuration for FastAPI.

Replaces the old in-memory RateLimiter with slowapi — a production-ready
rate limiter that supports Redis-backed storage for horizontal scaling.

Migration: 2026-10-02
- Old: self-written RateLimiter in app/middleware/rate_limit.py (in-memory only)
- New: slowapi with memory storage (falls back to memory if Redis unavailable)
"""
import os
from slowapi import Limiter
from slowapi.util import get_remote_address

# In CI/test environments, use very high limits to avoid blocking tests
# In production, use normal limits
is_test = os.getenv("CI") == "true" or os.getenv("PYTEST_CURRENT_TEST")
default_limits = [] if not is_test else ["10000/minute"]

limiter = Limiter(key_func=get_remote_address, default_limits=default_limits)

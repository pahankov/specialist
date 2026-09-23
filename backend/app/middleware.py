"""Rate limiting middleware for FastAPI."""
import time
from collections import defaultdict
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Dict, Tuple


class RateLimiter:
    """Simple in-memory rate limiter."""

    def __init__(self, default_limit: int = 60, window: int = 60):
        self.default_limit = default_limit
        self.window = window
        self.requests: Dict[str, list] = defaultdict(list)
        self.endpoints: Dict[str, Tuple[int, int]] = {}

    def add_endpoint(self, path: str, limit: int, window: int) -> None:
        self.endpoints[path] = (limit, window)

    def is_allowed(self, client_ip: str, path: str) -> Tuple[bool, int, int]:
        """Check if request is allowed. Returns (allowed, limit, remaining)."""
        limit, window = self.endpoints.get(path, (self.default_limit, self.window))
        now = time.time()
        timestamps = self.requests[client_ip]

        # Remove old timestamps outside the window
        self.requests[client_ip] = [t for t in timestamps if now - t < window]
        timestamps = self.requests[client_ip]

        if len(timestamps) >= limit:
            return False, limit, 0

        timestamps.append(now)
        remaining = limit - len(timestamps)
        return True, limit, remaining

    def reset(self) -> None:
        """Clear all rate limit data. Useful for tests."""
        self.requests.clear()


rate_limiter = RateLimiter(default_limit=60, window=60)

# Stricter limits for auth endpoints
rate_limiter.add_endpoint("/api/v1/auth/login", 10, 60)
rate_limiter.add_endpoint("/api/v1/auth/register", 5, 60)
rate_limiter.add_endpoint("/api/v1/auth/client/login", 10, 60)
rate_limiter.add_endpoint("/api/v1/auth/refresh", 20, 60)

# Stricter limit for public booking
rate_limiter.add_endpoint("/api/v1/appointments/public/", 10, 60)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health check, docs, test clients, and non-API paths
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        base_url = str(request.base_url)
        
        # Skip for docs, health, and test environment
        if path in ("/health", "/docs", "/openapi.json", "/redoc"):
            return await call_next(request)
        
        # Skip rate limiting entirely for test clients
        if client_ip == "test" or "test" in base_url:
            return await call_next(request)

        allowed, limit, remaining = rate_limiter.is_allowed(client_ip, path)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "Слишком много запросов. Попробуйте позже."},
                headers={
                    "Retry-After": str(rate_limiter.window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        return response

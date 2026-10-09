"""Request logging middleware — logs HTTP requests with method, path, status, duration."""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.logging_config import set_request_id

logger = logging.getLogger(__name__)

# Noise paths: liveness probes and interactive docs don't need per-request INFO.
SKIP_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every HTTP request with timing and correlation ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate unique ID for this request
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Set correlation ID in contextvars so all loggers pick it up
        set_request_id(request_id)

        quiet = request.url.path in SKIP_PATHS

        # Log request start (skip noise; IP/UA omitted — GDPR, path is enough)
        if not quiet:
            logger.info("%s %s", request.method, request.url.path)

        # Measure duration
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log response (errors always, even on quiet paths)
            if not quiet or response.status_code >= 500:
                log_level = logging.WARNING if response.status_code >= 500 else logging.INFO
                logger.log(
                    log_level,
                    "%s %s → %s | %dms",
                    request.method,
                    request.url.path,
                    response.status_code,
                    duration_ms,
                )

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "%s %s → ERROR | %dms | %s",
                request.method,
                request.url.path,
                duration_ms,
                exc,
                exc_info=True,  # Include traceback
            )
            # Exception path skips the normal exception handlers — return JSON
            # ourselves so X-Request-ID is present on 500s too.
            return JSONResponse(
                status_code=500,
                content={"detail": "Внутренняя ошибка сервера", "request_id": request_id},
                headers={"X-Request-ID": request_id},
            )

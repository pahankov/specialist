"""Request logging middleware — logs HTTP requests with method, path, status, duration."""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.logging_config import set_request_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that logs every HTTP request with timing and correlation ID."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Generate unique ID for this request
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Set correlation ID in contextvars so all loggers pick it up
        set_request_id(request_id)

        # Log request start
        logger.info(
            "%s %s | IP: %s | User-Agent: %s",
            request.method,
            request.url.path,
            request.client.host if request.client else "-",
            request.headers.get("user-agent", "-")[:100],
        )

        # Measure duration
        start_time = time.time()

        try:
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Log response
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
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                "%s %s → ERROR | %dms | %s",
                request.method,
                request.url.path,
                duration_ms,
                exc,
                exc_info=True,  # Include traceback
            )
            raise

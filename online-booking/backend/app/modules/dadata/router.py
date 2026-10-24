"""DAData suggestions proxy endpoint.

Frontend calls same-origin /api/dadata/<method> (dev: vite proxies it to
DaData directly; prod: nginx proxies it here). The secret never leaves
the backend: upstream auth uses server-side Settings.
"""
import logging
from typing import Any, Optional
import httpx
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse
from app.config import settings
from app.middleware.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# 4_1/rs matches the suggest/address contract used by the frontend
# (same shape as the vite dev proxy rewrite).
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs"

# Only the method the frontend actually uses. Without an allowlist the
# endpoint is an authenticated proxy to the whole DaData API: anyone could
# burn the account quota on party/bank/etc. requests.
ALLOWED_PATHS = frozenset({"suggest/address"})
ALLOWED_BODY_KEYS = frozenset({"query", "count", "locations", "from_bound", "to_bound"})
MAX_QUERY_LENGTH = 200
MAX_COUNT = 20


def _validate_body(body: Optional[Any]) -> None:
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Body must be a JSON object")
    extra = set(body) - ALLOWED_BODY_KEYS
    if extra:
        raise HTTPException(status_code=400, detail="Unsupported body fields")
    query = body.get("query")
    if not isinstance(query, str) or not query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    if len(query) > MAX_QUERY_LENGTH:
        raise HTTPException(status_code=400, detail="query is too long")
    count = body.get("count", 10)
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_COUNT:
        raise HTTPException(status_code=400, detail=f"count must be 1..{MAX_COUNT}")


@router.post("/{path:path}")
@limiter.limit("30/minute")
async def proxy_dadata(
    request: Request,
    path: str,
    body: Optional[Any] = Body(default=None),
):
    """Proxy requests to DAData API (forwards client payload, mirrors status)."""
    if path not in ALLOWED_PATHS:
        raise HTTPException(status_code=404, detail="Unknown DaData method")
    _validate_body(body)
    if not settings.DADATA_API_KEY or not settings.DADATA_SECRET:
        raise HTTPException(status_code=503, detail="DaData credentials not configured")
    target_url = f"{DADATA_URL}/{path}"

    headers = {
        "Authorization": f"Token {settings.DADATA_API_KEY}",
        "X-Secret": settings.DADATA_SECRET,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(target_url, headers=headers, json=body)
        except httpx.HTTPError as e:
            logger.error(f"DAData proxy error: {e}")
            raise HTTPException(status_code=502, detail="DaData upstream error")
        try:
            payload = response.json()
        except ValueError:
            payload = {"detail": f"DaData upstream error (status {response.status_code})"}
        return JSONResponse(status_code=response.status_code, content=payload)

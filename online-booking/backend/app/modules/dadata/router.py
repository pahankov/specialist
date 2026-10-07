"""DAData suggestions proxy endpoint.

Frontend calls same-origin /api/dadata/<method> (dev: vite proxies it to
DaData directly; prod: nginx proxies it here). The secret never leaves
the backend: upstream auth uses server-side Settings.
"""
import logging
from typing import Any, Optional
import httpx
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# 4_1/rs matches the suggest/address contract used by the frontend
# (same shape as the vite dev proxy rewrite).
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/4_1/rs"


@router.post("/{path:path}")
async def proxy_dadata(path: str, body: Optional[Any] = Body(default=None)):
    """Proxy requests to DAData API (forwards client payload, mirrors status)."""
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

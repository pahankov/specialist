"""DAData rich suggestions proxy endpoint."""
import logging
import os
from typing import Any, Optional
import httpx
from fastapi import APIRouter, Body, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter()

# Значения — из online-booking/backend/.env (канон) / LOCAL.md, never commit.
# В git только плейсхолдеры.
DADATA_TOKEN = os.getenv("DADATA_API_KEY", "")
DADATA_SECRET = os.getenv("DADATA_SECRET", "")
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/v4/rich"


@router.post("/{path:path}")
async def proxy_dadata(path: str, body: Optional[Any] = Body(default=None)):
    """Proxy requests to DAData API (forwards client payload)."""
    if not DADATA_TOKEN or not DADATA_SECRET:
        raise HTTPException(status_code=503, detail="DaData credentials not configured")
    target_url = f"{DADATA_URL}/{path}"

    headers = {
        "Authorization": f"Token {DADATA_TOKEN}",
        "X-Secret": DADATA_SECRET,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(target_url, headers=headers, json=body)
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"DAData proxy error: {e}")
            raise HTTPException(status_code=502, detail="DaData upstream error")

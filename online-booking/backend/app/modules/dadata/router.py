"""DAData rich suggestions proxy endpoint."""
import logging
import httpx
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()

DADATA_TOKEN = "REDACTED_DADATA_TOKEN"
DADATA_SECRET = "REDACTED_DADATA_SECRET"
DADATA_URL = "https://suggestions.dadata.ru/suggestions/api/v4/rich"


@router.post("/{path:path}")
async def proxy_dadata(path: str):
    """Proxy requests to DAData API."""
    target_url = f"{DADATA_URL}/{path}"
    
    headers = {
        "Authorization": f"Api Key {DADATA_TOKEN}",
        "X-Secret": DADATA_SECRET,
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(target_url, headers=headers, json=None)
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"DAData proxy error: {e}")
            raise

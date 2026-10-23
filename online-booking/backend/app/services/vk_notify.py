"""Best-effort VK user messages through a community access token."""
import secrets

import httpx

from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)

API_URL = "https://api.vk.com/method/messages.send"


async def send_vk_message(user_id: int, text: str) -> bool:
    if not settings.vk_notify_enabled:
        return False
    payload = {
        "user_ids": str(user_id),
        "message": (text or "")[:4000],
        "random_id": secrets.randbelow(2_000_000_000) + 1,
        "access_token": settings.VK_NOTIFY_TOKEN,
        "v": settings.VK_API_VERSION,
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(API_URL, data=payload)
            data = resp.json()
    except Exception as exc:
        logger.warning("VK message failed: user=%s error=%s", user_id, exc)
        return False
    if isinstance(data, dict) and data.get("error"):
        error = data["error"]
        logger.warning(
            "VK message rejected: user=%s code=%s msg=%s",
            user_id, error.get("error_code"), error.get("error_msg"),
        )
        return False
    logger.info("VK message sent: user=%s", user_id)
    return True

"""Self-healing MAX webhook subscription guard.

MAX auto-unsubscribes the bot if its webhook endpoint produces no
successful response within 8 hours (dev.max.ru, POST /subscriptions).
One outage window (deploys, the otp_codes 500s) is therefore enough to
silently kill ALL bot auth updates: the site still accepts /max/start,
but no `bot_started` / `message_created` ever reaches us, so no code is
delivered into the dialog and users are stuck.

This guard re-subscribes whenever the expected subscription is missing
or stale. It runs as a lifespan background loop (app.main) and is
enabled only when MAX auth is configured AND MAX_WEBHOOK_URL is set
(production); MAX API errors never raise — the loop just retries later.
"""
import asyncio

from app.config import settings
from app.logging_config import get_logger
from app.services.max_api import MaxApiError, get_max_api

logger = get_logger(__name__)

INTERVAL_SECONDS = 10 * 60

# Same set the subscribe helper registers (MaxBotApi.set_webhook).
# message_callback powers the in-chat «Начать заново» button (1.79.5):
# without it the tap never reaches us and the dialog stays dead-ended.
EXPECTED_UPDATE_TYPES = {"message_created", "bot_started", "message_callback"}


async def ensure_webhook_subscription(api=None) -> bool:
    """Re-subscribe when the expected subscription is missing or stale.

    Returns True when a (re)subscribe call was made — and succeeded.
    """
    if not (
        settings.max_enabled
        and settings.MAX_WEBHOOK_URL
        and settings.MAX_WEBHOOK_SECRET
    ):
        return False
    api = api or get_max_api()
    url = settings.MAX_WEBHOOK_URL
    try:
        data = await api.get_subscriptions()
    except MaxApiError as e:
        logger.warning("MAX webhook guard: subscription check failed: %s", e)
        return False
    for sub in data.get("subscriptions") or []:
        types = set(sub.get("update_types") or [])
        if sub.get("url") == url and EXPECTED_UPDATE_TYPES <= types:
            return False
    try:
        await api.set_webhook(url, settings.MAX_WEBHOOK_SECRET)
    except MaxApiError as e:
        logger.warning("MAX webhook guard: re-subscribe failed: %s", e)
        return False
    logger.warning("MAX webhook guard: subscription restored -> %s", url)
    return True


async def max_webhook_guard_loop() -> None:
    """Lifespan loop: verify at startup, then every INTERVAL_SECONDS."""
    while True:
        try:
            await ensure_webhook_subscription()
        except asyncio.CancelledError:
            raise
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("MAX webhook guard: unexpected error: %s", e)
        await asyncio.sleep(INTERVAL_SECONDS)

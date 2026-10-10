"""Manage the MAX webhook subscription (run once per environment).

Usage (from online-booking/backend, venv active):
    python max_webhook.py status       # show current subscriptions
    python max_webhook.py subscribe    # subscribe prod webhook URL
    python max_webhook.py unsubscribe  # remove subscription (dev/long-poll mode)

Environment (server .env / local .env, never hardcoded):
    MAX_BOT_TOKEN      - bot access token
    MAX_WEBHOOK_SECRET - value sent as X-Max-Bot-Api-Secret
    MAX_WEBHOOK_URL    - public webhook URL (default: https://beauty-specialist.ru/api/max/webhook)

Requires: MAX_BOT_TOKEN set, otherwise exits non-zero (fail fast).
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
# Settings reads backend/.env relative to CWD — anchor CWD to this script's
# dir so the script works from anywhere (repo root, cron, CI).
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.max_api import MaxApiError, MaxBotApi

DEFAULT_URL = "https://beauty-specialist.ru/api/max/webhook"


async def cmd_status(api: MaxBotApi) -> int:
    try:
        result = await api.get_subscriptions()
        print(f"Subscriptions: {result}")
        return 0
    except MaxApiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


async def cmd_subscribe(api: MaxBotApi, url: str) -> int:
    secret = settings.MAX_WEBHOOK_SECRET
    if not secret:
        print("ERROR: MAX_WEBHOOK_SECRET is not set - refusing insecure subscribe.",
              file=sys.stderr)
        return 1
    try:
        result = await api.set_webhook(url, secret)
        print(f"Subscribed: {url} -> {result}")
        return 0
    except MaxApiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


async def cmd_unsubscribe(api: MaxBotApi) -> int:
    try:
        result = await api.delete_webhook()
        print(f"Unsubscribed -> {result}")
        return 0
    except MaxApiError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


async def main() -> int:
    if not settings.MAX_BOT_TOKEN:
        print("ERROR: MAX_BOT_TOKEN is not set.", file=sys.stderr)
        return 1
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    url = os.getenv("MAX_WEBHOOK_URL", DEFAULT_URL)
    api = MaxBotApi()
    try:
        await api.get_me()
    except MaxApiError as e:
        print(f"ERROR: token check failed: {e}", file=sys.stderr)
        return 1
    if cmd == "subscribe":
        return await cmd_subscribe(api, url)
    if cmd == "unsubscribe":
        return await cmd_unsubscribe(api)
    return await cmd_status(api)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

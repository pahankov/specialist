"""Dev-only bridge: MAX long-poll -> local webhook.

Production uses a webhook subscription (MAX servers call us). Localhost is
not reachable from the internet, so for development this script polls
`GET /updates` itself and forwards every update to the local backend:

    python max_poll.py   (venv active, from online-booking/backend)

Full local test: start backend (`scripts\\start.bat`), run this script,
open the site, request a MAX code, send it to the bot — the site logs in.

Reads MAX_BOT_TOKEN / MAX_WEBHOOK_SECRET from backend/.env via settings.
Ctrl+C to stop. Prints markers/counts only — never tokens or codes.
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
# Settings reads backend/.env relative to CWD — anchor CWD to this script's
# dir so the poller works from anywhere (repo root, cron, CI).
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from app.config import settings
from app.services.max_api import MaxApiError, MaxBotApi

TARGET = os.getenv("MAX_POLL_TARGET", "http://127.0.0.1:8000/api/max/webhook")
POLL_TIMEOUT = int(os.getenv("MAX_POLL_TIMEOUT", "30"))


async def forward(update: dict) -> None:
    import httpx

    headers = {}
    if settings.MAX_WEBHOOK_SECRET:
        headers["X-Max-Bot-Api-Secret"] = settings.MAX_WEBHOOK_SECRET
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(TARGET, json=update, headers=headers)
    outcome = ""
    try:
        outcome = resp.json().get("outcome", "")
    except Exception:
        pass
    print(
        f"  -> local {resp.status_code} "
        f"({update.get('update_type')}{('/' + outcome) if outcome else ''})",
        flush=True,
    )


async def main() -> int:
    if not settings.MAX_BOT_TOKEN:
        print("ERROR: MAX_BOT_TOKEN is not set.", file=sys.stderr)
        return 1
    api = MaxBotApi()
    try:
        me = await api.get_me()
        print(f"Bot OK: @{me.get('username')} (polling, Ctrl+C to stop)")
    except MaxApiError as e:
        print(f"ERROR: token check failed: {e}", file=sys.stderr)
        return 1

    marker = None
    failures = 0
    while True:
        try:
            batch = await api.get_updates(marker=marker, timeout=POLL_TIMEOUT)
        except MaxApiError as e:
            failures += 1
            wait = min(5 * failures, 60)
            print(f"Poll error ({e}), retry in {wait}s...")
            await asyncio.sleep(wait)
            continue
        failures = 0
        updates = batch.get("updates") or []
        marker = batch.get("marker", marker)
        for update in updates:
            try:
                await forward(update)
            except Exception as e:
                print(f"  -> forward failed: {e} (update kept, will retry on next poll)")
                time.sleep(1)
        if updates:
            print(f"marker={marker} ({len(updates)} updates)", flush=True)


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nStopped.")

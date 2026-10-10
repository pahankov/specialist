"""MAX messenger chat-bot auth — SMS-alternative login for clients.

Flow: site takes the phone -> user shares the number with the bot ->
bot replies INTO the dialog with the code -> user types it on site ->
/max/verify mints the JWT session.
Exposes `router` (/api/v1/auth) and `webhook_router` (/api/max).
"""
from app.modules.maxauth.router import router, webhook_router

__all__ = ["router", "webhook_router"]

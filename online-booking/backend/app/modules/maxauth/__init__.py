"""MAX messenger chat-bot auth — SMS-alternative login for clients.

Flow: site shows a 6-digit code -> user sends it to the MAX bot ->
webhook confirms -> site polls /max/status -> JWT session.
Exposes `router` (/api/v1/auth) and `webhook_router` (/api/max).
"""
from app.modules.maxauth.router import router, webhook_router

__all__ = ["router", "webhook_router"]

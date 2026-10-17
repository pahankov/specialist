"""VK ID auth module (OAuth 2.0 Authorization Code Flow + PKCE).

Exposes `router` (/api/v1/auth/vk/*).
"""
from app.modules.vkauth.router import router

__all__ = ["router"]

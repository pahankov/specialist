"""Yandex ID auth module (OAuth 2.0 Authorization Code Flow).

Exposes `router` (/api/v1/auth/yandex/*).
"""
from app.modules.yandexauth.router import router

__all__ = ["router"]

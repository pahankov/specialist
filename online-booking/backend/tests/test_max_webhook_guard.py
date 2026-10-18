"""Tests for the MAX webhook subscription guard (self-healing re-subscribe).

No real MAX network: the API client is faked. The guard must re-subscribe
only when the expected subscription is missing/stale and must never raise
(a MAX hiccup must not kill the lifespan loop).
"""
import asyncio

import pytest

from app.services import max_webhook_guard as guard
from app.services.max_api import MaxApiError

URL = "https://example.test/api/max/webhook"


@pytest.fixture
def max_guard_cfg(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "MAX_WEBHOOK_SECRET", "test-secret")
    monkeypatch.setattr(settings, "MAX_WEBHOOK_URL", URL)


class FakeApi:
    def __init__(self, subscriptions=None, fail_check=False, fail_set=False):
        self._subscriptions = [] if subscriptions is None else subscriptions
        self._fail_check = fail_check
        self._fail_set = fail_set
        self.set_calls = []

    async def get_subscriptions(self):
        if self._fail_check:
            raise MaxApiError("API unreachable")
        return {"subscriptions": self._subscriptions}

    async def set_webhook(self, url, secret):
        if self._fail_set:
            raise MaxApiError("API unreachable")
        self.set_calls.append((url, secret))
        return {"success": True}


def _subscription(url=URL, update_types=("message_created", "bot_started")):
    return {"url": url, "update_types": list(update_types), "time": 1}


class TestEnsureWebhookSubscription:
    async def test_resubscribes_when_missing(self, max_guard_cfg):
        api = FakeApi(subscriptions=[])
        assert await guard.ensure_webhook_subscription(api) is True
        assert api.set_calls == [(URL, "test-secret")]

    async def test_noop_when_expected_present(self, max_guard_cfg):
        api = FakeApi(subscriptions=[_subscription()])
        assert await guard.ensure_webhook_subscription(api) is False
        assert api.set_calls == []

    async def test_noop_when_types_superset(self, max_guard_cfg):
        api = FakeApi(subscriptions=[_subscription(
            update_types=("message_created", "bot_started", "chat_created"))])
        assert await guard.ensure_webhook_subscription(api) is False
        assert api.set_calls == []

    async def test_resubscribes_when_wrong_url(self, max_guard_cfg):
        api = FakeApi(subscriptions=[_subscription(url="https://old.example/hook")])
        assert await guard.ensure_webhook_subscription(api) is True
        assert api.set_calls == [(URL, "test-secret")]

    async def test_resubscribes_when_types_incomplete(self, max_guard_cfg):
        api = FakeApi(subscriptions=[_subscription(update_types=("message_created",))])
        assert await guard.ensure_webhook_subscription(api) is True
        assert api.set_calls == [(URL, "test-secret")]

    async def test_check_error_is_quiet(self, max_guard_cfg):
        api = FakeApi(fail_check=True)
        assert await guard.ensure_webhook_subscription(api) is False
        assert api.set_calls == []

    async def test_set_error_is_quiet(self, max_guard_cfg):
        api = FakeApi(subscriptions=[], fail_set=True)
        assert await guard.ensure_webhook_subscription(api) is False
        assert api.set_calls == []

    async def test_disabled_without_url(self, max_guard_cfg, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "MAX_WEBHOOK_URL", "")
        api = FakeApi(subscriptions=[])
        assert await guard.ensure_webhook_subscription(api) is False
        assert api.set_calls == []

    async def test_disabled_without_token(self, max_guard_cfg, monkeypatch):
        from app.config import settings
        monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "")
        api = FakeApi(subscriptions=[])
        assert await guard.ensure_webhook_subscription(api) is False
        assert api.set_calls == []


class TestGuardLoop:
    async def test_loop_survives_errors_then_propagates_cancel(self, monkeypatch):
        calls = []

        async def fake_ensure(api=None):
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("boom")
            raise asyncio.CancelledError

        monkeypatch.setattr(guard, "ensure_webhook_subscription", fake_ensure)
        monkeypatch.setattr(guard, "INTERVAL_SECONDS", 0)
        with pytest.raises(asyncio.CancelledError):
            await guard.max_webhook_guard_loop()
        assert len(calls) == 2

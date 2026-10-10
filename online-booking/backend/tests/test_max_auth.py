"""Tests for MAX chat-bot auth (SMS alternative).

Covers: /max/start, /max/status polling, /api/max/webhook processing,
webhook secret check, parse_update_code unit cases. No real MAX network
(send_message is stubbed).
"""
import pytest


PHONE = "+79990001122"


@pytest.fixture
def max_enabled(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "test-token")
    monkeypatch.setattr(settings, "MAX_BOT_USERNAME", "test_bot")
    monkeypatch.setattr(settings, "MAX_BOT_URL", "https://max.ru/test_bot")
    monkeypatch.setattr(settings, "MAX_WEBHOOK_SECRET", "test-secret")


@pytest.fixture
def no_max(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_BOT_TOKEN", "")


@pytest.fixture
def stub_sender(monkeypatch):
    """Stub outbound bot replies; record texts instead of HTTP."""
    import sys
    # NOTE: `app.modules.maxauth.router` attribute on the package is the
    # APIRouter instance (re-exported in __init__), so grab the module object.
    max_router_mod = sys.modules["app.modules.maxauth.router"]

    sent = []

    class StubApi:
        async def send_message(self, user_id, text):
            sent.append({"user_id": user_id, "text": text})
            return {"ok": True}

    monkeypatch.setattr(max_router_mod, "get_max_api", lambda: StubApi())
    return sent


def _webhook_update(code_text, sender_id=777, first_name="Ivan"):
    return {
        "update_type": "message_created",
        "timestamp": 1700000000000,
        "chat_id": 1001,
        "message": {
            "sender": {"user_id": sender_id, "first_name": first_name,
                       "is_bot": False},
            "timestamp": 1700000000000,
            "body": {"text": code_text},
        },
    }


class TestMaxStart:
    async def test_start_disabled_without_token(self, client, no_max):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.status_code == 503

    async def test_start_returns_display_code(self, client, max_enabled):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["code"]) == 6 and data["code"].isdigit()
        assert data["expires_in"] > 0
        assert data["bot_username"] == "test_bot"
        assert data["bot_url"]

    async def test_start_rejects_bad_phone(self, client, max_enabled):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": "123"})
        assert resp.status_code == 422


class TestMaxWebhook:
    async def test_secret_mismatch_rejected(self, client, max_enabled, stub_sender):
        resp = await client.post(
            "/api/max/webhook", json=_webhook_update("123456"),
            headers={"X-Max-Bot-Api-Secret": "wrong"},
        )
        assert resp.status_code == 403

    async def test_unknown_code_replies_hint(self, client, max_enabled, stub_sender):
        resp = await client.post(
            "/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.status_code == 200
        resp = await client.post(
            "/api/max/webhook", json=_webhook_update("000000"),
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True, "outcome": "unknown"}
        assert stub_sender and "не найден" in stub_sender[0]["text"]

    async def test_bot_started_replies_instructions(
        self, client, max_enabled, stub_sender
    ):
        resp = await client.post(
            "/api/max/webhook",
            json={"update_type": "bot_started", "timestamp": 1, "chat_id": 5},
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert stub_sender and "код" in stub_sender[0]["text"]

    async def test_non_message_update_ignored(self, client, max_enabled, stub_sender):
        resp = await client.post(
            "/api/max/webhook",
            json={"update_type": "bot_stopped", "timestamp": 1, "chat_id": 5},
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert stub_sender == []


class TestMaxFullFlow:
    async def test_start_webhook_status_login(
        self, client, max_enabled, stub_sender
    ):
        start = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        code = start.json()["code"]

        pending = await client.post("/api/v1/auth/max/status", json={"phone": PHONE})
        assert pending.json()["status"] == "pending"

        hook = await client.post(
            "/api/max/webhook", json=_webhook_update(code),
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert hook.json()["outcome"] == "confirmed"
        assert "принят" in stub_sender[0]["text"]

        done = await client.post("/api/v1/auth/max/status", json={"phone": PHONE})
        body = done.json()
        assert body["status"] == "verified"
        assert body["access_token"]
        assert body["is_new_user"] is True
        assert "access_token=" in done.headers.get("set-cookie", "")

        # Replay: code consumed, session minted once
        again = await client.post("/api/v1/auth/max/status", json={"phone": PHONE})
        assert again.json()["status"] == "expired"

    async def test_second_login_reuses_user(
        self, client, max_enabled, stub_sender
    ):
        await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        hook_code = (await client.post(
            "/api/v1/auth/max/start", json={"phone": PHONE})).json()["code"]
        await client.post(
            "/api/max/webhook", json=_webhook_update(hook_code),
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        done = await client.post("/api/v1/auth/max/status", json={"phone": PHONE})
        assert done.json()["is_new_user"] is True

        code2 = (await client.post(
            "/api/v1/auth/max/start", json={"phone": PHONE})).json()["code"]
        await client.post(
            "/api/max/webhook", json=_webhook_update(code2),
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        done2 = await client.post("/api/v1/auth/max/status", json={"phone": PHONE})
        assert done2.json()["status"] == "verified"
        assert done2.json()["is_new_user"] is False


class TestParseUpdateCode:
    def test_valid_code(self):
        from app.modules.maxauth.service import parse_update_code
        code, sender = parse_update_code(_webhook_update("482910"))
        assert code == "482910"
        assert sender["user_id"] == 777

    def test_non_digit_ignored(self):
        from app.modules.maxauth.service import parse_update_code
        code, sender = parse_update_code(_webhook_update("hello"))
        assert code is None
        assert sender["user_id"] == 777

    def test_non_message_update(self):
        from app.modules.maxauth.service import parse_update_code
        assert parse_update_code({"update_type": "bot_stopped"}) == (None, None)
        assert parse_update_code({}) == (None, None)
        assert parse_update_code(None) == (None, None)

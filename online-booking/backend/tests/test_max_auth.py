"""Tests for MAX chat-bot auth (SMS-style flow).

Covers: /max/start (no code in response), /max/verify, /api/max/webhook
(phone/contact intake, HMAC, code delivery, keyboard), secret check,
pure parse helpers. No real MAX network (send_message is stubbed).
"""
import re

import pytest


PHONE = "+79990001122"
PHONE_NORM = "+7 (999) 000-11-22"  # as stored after schema normalization


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
    """Stub outbound bot replies; record (user_id, text, attachments)."""
    import sys
    max_router_mod = sys.modules["app.modules.maxauth.router"]

    sent = []

    class StubApi:
        async def send_message(self, user_id, text, attachments=None):
            sent.append({"user_id": user_id, "text": text,
                         "attachments": attachments})
            return {"ok": True}

    monkeypatch.setattr(max_router_mod, "get_max_api", lambda: StubApi())
    return sent


def _msg_update(text=None, sender_id=777, first_name="Ivan", contact=None):
    body = {}
    if text is not None:
        body["text"] = text
    if contact is not None:
        body["attachments"] = [{"type": "contact", "payload": contact}]
    return {
        "update_type": "message_created",
        "timestamp": 1700000000000,
        "chat_id": 1001,
        "message": {
            "sender": {"user_id": sender_id, "first_name": first_name,
                       "is_bot": False},
            "timestamp": 1700000000000,
            "body": body,
        },
    }


def _hook(client, update):
    return client.post(
        "/api/max/webhook", json=update,
        headers={"X-Max-Bot-Api-Secret": "test-secret"},
    )


async def _request_code(client, phone=PHONE):
    """Site step 1 -> bot step (typed phone) -> extract delivered code."""
    start = await client.post("/api/v1/auth/max/start", json={"phone": phone})
    assert start.status_code == 200
    return start


class TestMaxStart:
    async def test_start_disabled_without_token(self, client, no_max):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.status_code == 503

    async def test_start_returns_no_code(self, client, max_enabled):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.status_code == 200
        data = resp.json()
        assert "code" not in data  # code goes to the MAX dialog, never the site
        assert data["expires_in"] > 0
        assert data["bot_username"] == "test_bot"
        assert data["bot_url"]

    async def test_start_rejects_bad_phone(self, client, max_enabled):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": "123"})
        assert resp.status_code == 422


class TestMaxWebhook:
    async def test_secret_mismatch_rejected(self, client, max_enabled, stub_sender):
        resp = await client.post(
            "/api/max/webhook", json=_msg_update("123456"),
            headers={"X-Max-Bot-Api-Secret": "wrong"},
        )
        assert resp.status_code == 403

    async def test_bot_started_sends_keyboard(
        self, client, max_enabled, stub_sender
    ):
        resp = await client.post(
            "/api/max/webhook",
            json={"update_type": "bot_started", "timestamp": 1, "chat_id": 5,
                  "message": {"sender": {"user_id": 9}}},
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert resp.status_code == 200
        assert stub_sender
        buttons = stub_sender[0]["attachments"][0]["payload"]["buttons"]
        assert buttons[0][0]["type"] == "request_contact"

    async def test_typed_phone_gets_code(
        self, client, max_enabled, stub_sender
    ):
        await _request_code(client)
        resp = await _hook(client, _msg_update("+79990001122"))
        assert resp.json()["outcome"] == "delivered"
        assert stub_sender
        code = re.search(r"\d{6}", stub_sender[0]["text"])
        assert code, stub_sender[0]["text"]

    async def test_phone_without_pending_gets_hint(
        self, client, max_enabled, stub_sender
    ):
        resp = await _hook(client, _msg_update("+79990009999"))
        assert resp.json() == {"ok": True, "outcome": "no_pending"}
        assert stub_sender and "на сайте" in stub_sender[0]["text"]

    async def test_non_phone_text_gets_hint(
        self, client, max_enabled, stub_sender
    ):
        resp = await _hook(client, _msg_update("hello"))
        assert resp.status_code == 200
        assert stub_sender and "номер" in stub_sender[0]["text"]

    async def test_contact_share_verified_flow(
        self, client, max_enabled, stub_sender, session
    ):
        import hashlib
        import hmac as hmac_mod

        await _request_code(client)
        vcf = ("BEGIN:VCARD\r\nVERSION:3.0\r\n"
               "TEL;TYPE=cell:79990001122\r\nFN:Ivan\r\nEND:VCARD\r\n")
        digest = hmac_mod.new(b"test-token", vcf.encode(),
                              hashlib.sha256).hexdigest()
        resp = await _hook(client, _msg_update(
            None, contact={"vcf_info": vcf, "hash": digest}))
        assert resp.json()["outcome"] == "delivered"

        from sqlalchemy import select
        from app.models.otp_code import OtpCode
        rows = (await session.execute(
            select(OtpCode).where(OtpCode.phone == PHONE_NORM))).scalars().all()
        assert rows and rows[-1].max_verified_phone is True

    async def test_contact_bad_hmac_unverified(
        self, client, max_enabled, stub_sender, session
    ):
        await _request_code(client)
        vcf = ("BEGIN:VCARD\r\nVERSION:3.0\r\n"
               "TEL;TYPE=cell:79990001122\r\nFN:Ivan\r\nEND:VCARD\r\n")
        resp = await _hook(client, _msg_update(
            None, contact={"vcf_info": vcf, "hash": "0" * 64}))
        # HMAC mismatch -> treated as unverified typed-equivalent, code still delivered
        assert resp.json()["outcome"] == "delivered"

        from sqlalchemy import select
        from app.models.otp_code import OtpCode
        rows = (await session.execute(
            select(OtpCode).where(OtpCode.phone == PHONE_NORM))).scalars().all()
        assert rows and rows[-1].max_verified_phone is False


class TestMaxVerify:
    async def _delivered_code(self, client, stub_sender, phone=PHONE):
        await _request_code(client, phone)
        await _hook(client, _msg_update(phone))
        assert stub_sender
        return re.search(r"\d{6}", stub_sender[-1]["text"]).group(0)

    async def test_full_flow_new_user(
        self, client, max_enabled, stub_sender
    ):
        code = await self._delivered_code(client, stub_sender)
        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert done.status_code == 200
        body = done.json()
        assert body["access_token"]
        assert body["is_new_user"] is True
        assert "access_token=" in done.headers.get("set-cookie", "")

        # Replay: code consumed
        again = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert again.status_code == 400

    async def test_second_login_reuses_user(
        self, client, max_enabled, stub_sender
    ):
        code = await self._delivered_code(client, stub_sender)
        first = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert first.json()["is_new_user"] is True

        await _request_code(client)
        await _hook(client, _msg_update(PHONE))
        code2 = re.search(r"\d{6}", stub_sender[-1]["text"]).group(0)
        second = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code2})
        assert second.status_code == 200
        assert second.json()["is_new_user"] is False

    async def test_wrong_code_rejected(self, client, max_enabled, stub_sender):
        await self._delivered_code(client, stub_sender)
        resp = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": "000000"})
        assert resp.status_code == 400

    async def test_expired_code_rejected(
        self, client, max_enabled, stub_sender, session
    ):
        import datetime
        code = await self._delivered_code(client, stub_sender)
        from sqlalchemy import update as sa_update
        from app.models.otp_code import OtpCode
        await session.execute(
            sa_update(OtpCode)
            .where(OtpCode.phone == PHONE_NORM, OtpCode.channel == "max")
            .values(expires_at=datetime.datetime(2000, 1, 1)))
        await session.commit()
        resp = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert resp.status_code == 410

    async def test_unconfirmed_code_rejected(self, client, max_enabled):
        await _request_code(client)
        # Code never delivered to dialog (no webhook) -> must not verify.
        # Brute-guessing is the only path; any code fails the hash check
        # unless the bot delivered it (hash was rotated on delivery).
        resp = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": "123456"})
        assert resp.status_code in (400, 410)

    async def test_verify_disabled_without_token(self, client, no_max):
        resp = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": "123456"})
        assert resp.status_code == 503


class TestParseHelpers:
    def test_parse_phone_text(self):
        from app.modules.maxauth.service import parse_phone_text
        assert parse_phone_text("+7 (999) 123-45-67") == "+7 (999) 123-45-67"
        assert parse_phone_text("89991234567") == "+7 (999) 123-45-67"
        assert parse_phone_text("hello") is None
        assert parse_phone_text("12345") is None

    def test_parse_contact_no_attachment(self):
        from app.modules.maxauth.service import parse_contact_phone
        assert parse_contact_phone({}) == (None, False, "")
        assert parse_contact_phone({"body": {}}) == (None, False, "")

    def test_sender_display_name(self):
        from app.modules.maxauth.service import sender_display_name
        assert sender_display_name({"first_name": "A", "last_name": "B"}) == "A B"
        assert sender_display_name({}) == ""

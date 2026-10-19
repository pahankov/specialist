"""Tests for MAX chat-bot auth (SMS-style flow).

Covers: /max/start (no code in response), /max/verify, /api/max/webhook
(contact intake, HMAC, keyboard hints), secret check, pure parse helpers,
plus takeover regressions: deeplink opens and typed numbers never deliver
a code, only an HMAC-verified contact share does. No real MAX network
(send_message is stubbed).
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
    monkeypatch.setattr(settings, "MAX_BOT_NAME", "Электронная запись")
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

        async def answer_callback(self, callback_id, notification=None):
            sent.append({"answer_callback": callback_id,
                         "notification": notification})
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


def _callback_update(callback_id="cb-1", payload="restart", user_id=4242):
    """Inline button tap (message_callback) inside the dialog."""
    return {
        "update_type": "message_callback",
        "timestamp": 1700000000000,
        "callback": {
            "callback_id": callback_id,
            "payload": payload,
            "sender": {"user_id": user_id, "first_name": "Ivan"},
            "message": {"body": {"mid": "m1"},
                        "recipient": {"chat_id": 1001}},
        },
    }


async def _request_code(client, phone=PHONE):
    """Site step 1: register a pending code request (no code in response)."""
    start = await client.post("/api/v1/auth/max/start", json={"phone": phone})
    assert start.status_code == 200
    return start


def _vcf_and_digest(phone=PHONE):
    """vCard + matching HMAC for a contact share (token = test-token)."""
    import hashlib
    import hmac as hmac_mod

    vcf = ("BEGIN:VCARD\r\nVERSION:3.0\r\n"
           f"TEL;TYPE=cell:{phone.lstrip('+')}\r\nFN:Ivan\r\nEND:VCARD\r\n")
    digest = hmac_mod.new(b"test-token", vcf.encode(),
                          hashlib.sha256).hexdigest()
    return vcf, digest


async def _share_contact(client, phone=PHONE, sender_id=777):
    """HMAC-verified «Поделиться номером» tap in the dialog."""
    vcf, digest = _vcf_and_digest(phone)
    return await _hook(client, _msg_update(
        None, sender_id=sender_id, contact={"vcf_info": vcf, "hash": digest}))


class TestMaxStart:
    async def test_start_disabled_without_token(self, client, no_max):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.status_code == 503

    async def test_start_returns_no_code(self, client, max_enabled):
        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.status_code == 200
        data = resp.json()
        assert "code" not in data  # code goes to the MAX dialog, never the site
        assert data["delivered"] is False  # unknown dialog: share-number flow
        assert data["deeplink"].startswith("https://max.ru/test_bot?start=")
        assert data["expires_in"] > 0
        assert data["bot_username"] == "test_bot"
        assert data["bot_url"]
        assert data["bot_name"] == "Электронная запись"

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

    async def test_deeplink_open_asks_to_share_then_delivers(
        self, client, max_enabled, stub_sender
    ):
        """Deeplink open proves nothing about the phone: the bot asks to
        share the number; the code arrives only after the verified share."""
        start = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        payload = start.json()["deeplink"].split("?start=")[1]

        hook = await _hook(client, {
            "update_type": "bot_started", "timestamp": 1, "chat_id": 1001,
            "user": {"user_id": 4242, "first_name": "Deep"},
            "payload": payload,
        })
        assert hook.json()["outcome"] == "share_required"
        assert not re.search(r"\d{6}", stub_sender[0]["text"])
        buttons = stub_sender[0]["attachments"][0]["payload"]["buttons"]
        assert buttons[0][0]["type"] == "request_contact"

        share = await _share_contact(client, sender_id=4242)
        assert share.json()["outcome"] == "delivered"
        code = re.search(r"\d{6}", stub_sender[1]["text"]).group(0)
        # The code message carries the «Начать заново» restart button.
        code_buttons = stub_sender[1]["attachments"][0]["payload"]["buttons"]
        assert code_buttons[1][0]["type"] == "callback"

        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert done.status_code == 200
        assert done.json()["is_new_user"] is True

    async def test_deeplink_tampered_falls_back_to_keyboard(
        self, client, max_enabled, stub_sender
    ):
        start = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        payload = start.json()["deeplink"].split("?start=")[1]
        bad = payload[:-1] + ("0" if payload[-1] != "0" else "1")

        hook = await client.post(
            "/api/max/webhook",
            json={"update_type": "bot_started", "timestamp": 1, "chat_id": 1001,
                  "user": {"user_id": 4242}, "payload": bad},
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert hook.json() == {"ok": True}  # no outcome: keyboard path
        buttons = stub_sender[0]["attachments"][0]["payload"]["buttons"]
        assert buttons[0][0]["type"] == "request_contact"

    async def test_reply_prefers_update_user_over_chat(
        self, client, max_enabled, stub_sender
    ):
        """bot_started reply goes to update.user, not a stale chat_id."""
        hook = await client.post(
            "/api/max/webhook",
            json={"update_type": "bot_started", "timestamp": 1, "chat_id": 9999,
                  "user": {"user_id": 4242}},
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert hook.status_code == 200
        assert stub_sender
        assert stub_sender[0]["user_id"] == 4242

    async def test_dialog_not_found_retries_once(
        self, client, max_enabled, monkeypatch
    ):
        """Transient dialog.not.found (dialog creation race) is retried once."""
        import sys
        from app.services.max_api import MaxApiError
        mod = sys.modules["app.modules.maxauth.router"]
        monkeypatch.setattr(mod, "DIALOG_RETRY_DELAY", 0)

        calls = []

        class FlakyApi:
            async def send_message(self, user_id, text, attachments=None):
                calls.append(user_id)
                if len(calls) == 1:
                    raise MaxApiError(
                        'MAX API 404: {"code":"dialog.not.found"}')
                return {"ok": True}

        monkeypatch.setattr(mod, "get_max_api", lambda: FlakyApi())
        hook = await client.post(
            "/api/max/webhook",
            json={"update_type": "bot_started", "timestamp": 1, "chat_id": 1001,
                  "user": {"user_id": 4242}},
            headers={"X-Max-Bot-Api-Secret": "test-secret"},
        )
        assert hook.status_code == 200  # best-effort: webhook still 200
        assert calls == [4242, 4242]

    async def test_typed_phone_never_gets_code(
        self, client, max_enabled, stub_sender
    ):
        """A typed number is self-asserted: share button only, no code."""
        await _request_code(client)
        resp = await _hook(client, _msg_update(PHONE))
        assert resp.json()["outcome"] == "share_required"
        assert stub_sender
        assert not re.search(r"\d{6}", stub_sender[0]["text"])
        buttons = stub_sender[0]["attachments"][0]["payload"]["buttons"]
        assert buttons[0][0]["type"] == "request_contact"

    async def test_typed_phone_without_pending_gets_hint(
        self, client, max_enabled, stub_sender
    ):
        """Self-asserted number with no site request: share button only."""
        resp = await _hook(client, _msg_update("+79990009999"))
        assert resp.json() == {"ok": True, "outcome": "share_required"}
        assert stub_sender and "Поделиться номером" in stub_sender[0]["text"]
        assert not re.search(r"\d{6}", stub_sender[0]["text"])

    async def test_non_phone_text_gets_hint_with_keyboard(
        self, client, max_enabled, stub_sender
    ):
        """Hint repeats the request_contact button (first one is easy to miss)."""
        resp = await _hook(client, _msg_update("hello"))
        assert resp.json()["outcome"] == "share_required"
        assert stub_sender and "номер" in stub_sender[0]["text"]
        buttons = stub_sender[0]["attachments"][0]["payload"]["buttons"]
        assert buttons[0][0]["type"] == "request_contact"

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

    async def test_contact_carries_username_and_email(
        self, client, max_enabled, stub_sender, session
    ):
        """@nickname from sender + EMAIL from vCard land on the OTP row."""
        import hashlib
        import hmac as hmac_mod

        vcf = ("BEGIN:VCARD\r\nVERSION:3.0\r\n"
               "FN:Ivan\r\nTEL;TYPE=cell:79990001122\r\n"
               "EMAIL;TYPE=INTERNET:ivan@Example.COM\r\nEND:VCARD\r\n")
        digest = hmac_mod.new(b"test-token", vcf.encode(),
                              hashlib.sha256).hexdigest()
        update = _msg_update(None, contact={"vcf_info": vcf, "hash": digest})
        update["message"]["sender"]["username"] = "ivan_max"
        resp = await _hook(client, update)
        assert resp.json()["outcome"] == "delivered"
        code = re.search(r"\d{6}", stub_sender[0]["text"]).group(0)

        done = await client.post(
            "/api/v1/auth/max/verify",
            json={"phone": PHONE, "code": code, "consent": True})
        assert done.status_code == 200

        from sqlalchemy import select
        from app.models.user import User
        user = (await session.execute(
            select(User).where(User.phone == PHONE_NORM))).scalar_one()
        assert user.max_username == "ivan_max"
        assert user.email == "ivan@example.com"  # normalized to lowercase

    async def test_contact_bad_hmac_unverified(
        self, client, max_enabled, stub_sender, session
    ):
        """HMAC mismatch is NOT platform-proven: no code, share hint only."""
        await _request_code(client)
        vcf, _ = _vcf_and_digest()
        resp = await _hook(client, _msg_update(
            None, contact={"vcf_info": vcf, "hash": "0" * 64}))
        assert resp.json()["outcome"] == "share_required"
        assert not re.search(r"\d{6}", stub_sender[0]["text"])
        assert "подтвердить номер" in stub_sender[0]["text"]

        from sqlalchemy import select
        from app.models.otp_code import OtpCode
        otp = (await session.execute(
            select(OtpCode).where(OtpCode.phone == PHONE_NORM))).scalar_one()
        assert otp.max_user_id is None  # nothing bound, no code delivered

    async def test_contact_share_opens_request_without_site(
        self, client, max_enabled, stub_sender, session
    ):
        """HMAC-proven share needs no site step: the platform vouches the number."""
        import hashlib
        import hmac as hmac_mod

        vcf = ("BEGIN:VCARD\r\nVERSION:3.0\r\n"
               "TEL;TYPE=cell:79990001122\r\nFN:Ivan\r\nEND:VCARD\r\n")
        digest = hmac_mod.new(b"test-token", vcf.encode(),
                              hashlib.sha256).hexdigest()
        resp = await _hook(client, _msg_update(
            None, contact={"vcf_info": vcf, "hash": digest}))
        assert resp.json()["outcome"] == "delivered"
        assert stub_sender
        code = re.search(r"\d{6}", stub_sender[0]["text"]).group(0)

        done = await client.post(
            "/api/v1/auth/max/verify",
            json={"phone": PHONE, "code": code, "consent": True})
        assert done.status_code == 200
        assert done.json()["is_new_user"] is True

        from sqlalchemy import select
        from app.models.user import User
        from app.models.user_contact import UserContact
        user = (await session.execute(
            select(User).where(User.phone == PHONE_NORM))).scalar_one()
        assert user.consent_at is not None  # 152-FZ checkbox
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.contact_type == "phone",
                UserContact.value == PHONE_NORM))).scalar_one()
        assert contact.is_verified is True  # HMAC-proven number
        assert contact.verified_via == "social"
        assert contact.is_primary is True

    async def test_typed_phone_still_needs_site_request(
        self, client, max_enabled, stub_sender, session
    ):
        """Self-asserted numbers must not open requests on their own."""
        from sqlalchemy import func, select
        from app.models.otp_code import OtpCode

        resp = await _hook(client, _msg_update("+79990009999"))
        assert resp.json()["outcome"] == "share_required"
        assert not re.search(r"\d{6}", stub_sender[0]["text"])
        count = (await session.execute(
            select(func.count()).select_from(OtpCode)
            .where(OtpCode.channel == "max")
        )).scalar_one()
        assert count == 0


class TestMaxCallbackRestart:
    """1.79.5: «Начать заново» under the code message re-issues the share
    keyboard (MAX consumes request_contact after its first use)."""

    async def test_callback_restarts_share_flow(
        self, client, max_enabled, stub_sender
    ):
        resp = await _hook(client, _callback_update())
        assert resp.json()["outcome"] == "share_required"
        answers = [s for s in stub_sender if "answer_callback" in s]
        msgs = [s for s in stub_sender if "attachments" in s]
        assert answers == [{
            "answer_callback": "cb-1",
            "notification": "Отправляю кнопку ещё раз…",
        }]
        assert msgs and msgs[0]["user_id"] == 4242
        buttons = msgs[0]["attachments"][0]["payload"]["buttons"]
        assert buttons[0][0]["type"] == "request_contact"

    async def test_callback_without_sender_is_ignored(
        self, client, max_enabled, stub_sender
    ):
        update = _callback_update()
        update["callback"]["sender"] = {}
        resp = await _hook(client, update)
        assert resp.json() == {"ok": True}
        assert stub_sender == []

    async def test_callback_ack_failure_is_quiet(
        self, client, max_enabled, monkeypatch
    ):
        """A failed /answers must not stop the keyboard re-issue."""
        import sys
        from app.services.max_api import MaxApiError
        mod = sys.modules["app.modules.maxauth.router"]
        sent = []

        class HalfApi:
            async def send_message(self, user_id, text, attachments=None):
                sent.append(("message", user_id))
                return {"ok": True}

            async def answer_callback(self, callback_id, notification=None):
                raise MaxApiError("MAX API 400: callback expired")

        monkeypatch.setattr(mod, "get_max_api", lambda: HalfApi())
        resp = await _hook(client, _callback_update())
        assert resp.status_code == 200
        assert resp.json()["outcome"] == "share_required"
        assert sent == [("message", 4242)]


class TestBuildCodeMessage:
    def test_code_message_carries_copy_and_restart_buttons(self):
        from app.modules.maxauth.service import (
            RESTART_CALLBACK, build_code_message,
        )

        text, attachments = build_code_message("123456")
        assert "123456" in text
        buttons = attachments[0]["payload"]["buttons"]
        assert buttons[0][0]["type"] == "clipboard"
        assert buttons[0][0]["payload"] == "123456"
        assert buttons[1][0]["type"] == "callback"
        assert buttons[1][0]["payload"] == RESTART_CALLBACK


class TestTakeoverRegression:
    """Regressions for the pre-1.78.3 takeover hole: a code must never be
    delivered to a dialog that only opened a deeplink or typed the number."""

    async def _make_victim(self, session):
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        victim = User(
            name="Victim", phone=PHONE_NORM,
            hashed_password=hash_password("victim-pass"),
            role=UserRole.CLIENT, is_verified=True,
        )
        session.add(victim)
        await session.commit()
        await session.refresh(victim)
        return victim

    async def test_typed_spoof_cannot_takeover(
        self, client, max_enabled, stub_sender, session
    ):
        """A foreign dialog typing the victim's number gets no code."""
        victim = await self._make_victim(session)
        await _request_code(client)

        resp = await _hook(client, _msg_update(PHONE, sender_id=999999))
        assert resp.json()["outcome"] == "share_required"
        assert not re.search(r"\d{6}", stub_sender[0]["text"])

        # Any code fails: nothing was delivered to a dialog.
        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": "000000"})
        assert done.status_code == 400
        await session.refresh(victim)
        assert victim.max_user_id is None  # account untouched

    async def test_deeplink_spoof_cannot_takeover(
        self, client, max_enabled, stub_sender, session
    ):
        """A foreign MAX account opening the victim's deeplink gets no code."""
        victim = await self._make_victim(session)
        start = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        payload = start.json()["deeplink"].split("?start=")[1]

        hook = await _hook(client, {
            "update_type": "bot_started", "timestamp": 1, "chat_id": 666,
            "user": {"user_id": 999999, "first_name": "Attacker"},
            "payload": payload,
        })
        assert hook.json()["outcome"] == "share_required"
        assert not re.search(r"\d{6}", stub_sender[0]["text"])

        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": "000000"})
        assert done.status_code == 400
        await session.refresh(victim)
        assert victim.max_user_id is None  # account untouched


class TestMaxVerify:
    async def _delivered_code(self, client, stub_sender, phone=PHONE):
        """Site request + HMAC-verified share -> code from the dialog."""
        await _request_code(client, phone)
        await _share_contact(client, phone)
        assert stub_sender
        return re.search(r"\d{6}", stub_sender[-1]["text"]).group(0)

    async def test_full_flow_new_user(
        self, client, max_enabled, stub_sender, session
    ):
        """New number → consent challenge → consent/complete → session.

        152-FZ (owner item 6): no session before the user accepts the
        policy; the welcome bell arrives with the completed registration
        (owner item 5).
        """
        from sqlalchemy import select
        from app.models.user import User
        from app.models.notification import Notification

        code = await self._delivered_code(client, stub_sender)
        pending = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert pending.status_code == 200
        body = pending.json()
        assert body["is_new_user"] is True
        assert body["challenge"]  # consent required — no session yet
        assert "access_token=" not in pending.headers.get("set-cookie", "")

        # Consent cannot be skipped.
        denied = await client.post(
            "/api/v1/auth/consent/complete",
            json={"challenge": body["challenge"], "consent": False})
        assert denied.status_code == 400

        done = await client.post(
            "/api/v1/auth/consent/complete",
            json={"challenge": body["challenge"], "consent": True})
        assert done.status_code == 201
        assert done.json()["access_token"]
        assert "access_token=" in done.headers.get("set-cookie", "")

        user = (await session.execute(
            select(User).where(User.phone == PHONE_NORM))).scalar_one()
        assert user.consent_at is not None
        welcome = (await session.execute(
            select(Notification).where(
                Notification.recipient_id == user.id,
                Notification.audience == "system"))).scalars().all()
        assert welcome and "Добро пожаловать" in welcome[0].text

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
        await _share_contact(client)
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

    async def test_verify_hints_when_code_is_for_another_number(
        self, client, max_enabled, stub_sender
    ):
        """Typed phone A, shared number B: the error names the real number
        (share sends the MAX account's own phone) — no session is minted."""
        other = "+79995554433"
        code = await self._delivered_code(client, stub_sender)  # for PHONE

        resp = await client.post(
            "/api/v1/auth/max/verify", json={"phone": other, "code": code})
        assert resp.status_code == 400
        # The hint names the number the code was actually sent to.
        assert PHONE_NORM in resp.json()["detail"]

        # The hint consumes nothing: the right number still logs in.
        ok = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert ok.status_code == 200

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

    async def test_master_login_via_max(
        self, client, max_enabled, stub_sender, session
    ):
        """Existing master/admin enters by their account phone — role kept."""
        import jwt as pyjwt
        from app.config import settings
        from app.models.user import User, UserRole
        from app.models.master_profile import MasterProfile
        from app.utils.security import hash_password
        from datetime import datetime, timezone

        user = User(
            name="Master", email="master@example.com", phone=PHONE_NORM,
            hashed_password=hash_password("Password1!"),
            role=UserRole.MASTER, is_active=True, is_verified=True,
            # An existing account (consent tracked) — the consent overlay
            # is only for new/pending accounts.
            consent_at=datetime.now(timezone.utc),
        )
        session.add(user)
        await session.flush()
        session.add(MasterProfile(user_id=user.id))
        await session.commit()

        code = await self._delivered_code(client, stub_sender)
        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert done.status_code == 200
        body = done.json()
        assert body["is_new_user"] is False
        payload = pyjwt.decode(
            body["access_token"], settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM])
        assert payload["role"] == "MASTER"

    async def test_push_to_bound_dialog(
        self, client, max_enabled, stub_sender, session
    ):
        """Known dialog: start pushes the code straight into MAX."""
        from app.models.user import User, UserRole

        session.add(User(
            name="Bound", email="bound@example.com", phone=PHONE_NORM,
            hashed_password=None, role=UserRole.CLIENT,
            is_active=True, is_verified=True, max_user_id=555,
        ))
        await session.commit()

        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.json()["delivered"] is True
        assert stub_sender
        assert stub_sender[0]["user_id"] == 555
        code = re.search(r"\d{6}", stub_sender[0]["text"]).group(0)

        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False

    async def test_verify_links_max_account(
        self, client, max_enabled, stub_sender, session
    ):
        """First MAX login binds the sender id to a pre-existing account."""
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        session.add(User(
            name="Plain", email="plain@example.com", phone=PHONE_NORM,
            hashed_password=hash_password("Password1!"),
            role=UserRole.CLIENT, is_active=True, is_verified=False,
        ))
        await session.commit()

        code = await self._delivered_code(client, stub_sender)
        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert done.status_code == 200
        user = (await session.execute(
            select(User).where(User.phone == PHONE_NORM))).scalar_one()
        assert user.max_user_id == 777  # webhook sender from _msg_update

    async def test_contact_share_verifies_existing_user(
        self, client, max_enabled, stub_sender, session
    ):
        """HMAC-proven contact marks the phone verified for an existing account."""
        import hashlib
        import hmac as hmac_mod
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        session.add(User(
            name="Legacy", email="legacy@example.com", phone=PHONE_NORM,
            hashed_password=hash_password("Password1!"),
            role=UserRole.CLIENT, is_active=True, is_verified=False,
        ))
        await session.commit()

        vcf = ("BEGIN:VCARD\r\nVERSION:3.0\r\n"
               "TEL;TYPE=cell:79990001122\r\nFN:Ivan\r\nEND:VCARD\r\n")
        digest = hmac_mod.new(b"test-token", vcf.encode(),
                              hashlib.sha256).hexdigest()
        resp = await _hook(client, _msg_update(
            None, contact={"vcf_info": vcf, "hash": digest}))
        assert resp.json()["outcome"] == "delivered"
        code = re.search(r"\d{6}", stub_sender[-1]["text"]).group(0)

        done = await client.post(
            "/api/v1/auth/max/verify", json={"phone": PHONE, "code": code})
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False
        user = (await session.execute(
            select(User).where(User.phone == PHONE_NORM))).scalar_one()
        assert user.max_user_id == 777
        from app.models.user_contact import UserContact
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.contact_type == "phone",
                UserContact.value == PHONE_NORM))).scalar_one()
        assert contact.is_verified is True
        assert contact.verified_via == "social"
        assert contact.user_id == user.id

    async def test_bound_user_shares_new_phone_keeps_account(
        self, client, max_enabled, stub_sender, session
    ):
        """MAX id wins: a new shared phone does not fork a second account."""
        import hashlib
        import hmac as hmac_mod
        from sqlalchemy import func, select
        from app.models.user import User, UserRole
        from app.models.user_contact import UserContact

        bound = User(name="Bound", role=UserRole.CLIENT, is_active=True,
                     max_user_id=777, phone="+7 (900) 111-22-33")
        session.add(bound)
        await session.commit()

        vcf = ("BEGIN:VCARD\r\nVERSION:3.0\r\n"
               "TEL;TYPE=cell:79995554433\r\nFN:Ivan\r\nEND:VCARD\r\n")
        digest = hmac_mod.new(b"test-token", vcf.encode(),
                              hashlib.sha256).hexdigest()
        resp = await _hook(client, _msg_update(
            None, contact={"vcf_info": vcf, "hash": digest}))
        assert resp.json()["outcome"] == "delivered"
        code = re.search(r"\d{6}", stub_sender[-1]["text"]).group(0)

        done = await client.post(
            "/api/v1/auth/max/verify",
            json={"phone": "+79995554433", "code": code})
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False

        # The new number joined the SAME account as a verified contact.
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.value == "+7 (999) 555-44-33"))).scalar_one()
        assert contact.user_id == bound.id
        assert contact.is_verified is True
        # …and no duplicate account was created.
        users_total = (await session.execute(
            select(func.count()).select_from(User))).scalar_one()
        assert users_total == 1

    async def test_consent_backfilled_on_login(
        self, client, max_enabled, stub_sender, session
    ):
        """Legacy NULL-consent account gains consent when the form is checked."""
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.utils.security import hash_password

        session.add(User(
            name="Old", email="old@example.com", phone=PHONE_NORM,
            hashed_password=hash_password("Password1!"),
            role=UserRole.CLIENT, is_active=True, is_verified=False,
            max_user_id=555,
        ))
        await session.commit()

        resp = await client.post("/api/v1/auth/max/start", json={"phone": PHONE})
        assert resp.json()["delivered"] is True
        code = re.search(r"\d{6}", stub_sender[-1]["text"]).group(0)

        done = await client.post(
            "/api/v1/auth/max/verify",
            json={"phone": PHONE, "code": code, "consent": True})
        assert done.status_code == 200
        user = (await session.execute(
            select(User).where(User.phone == PHONE_NORM))).scalar_one()
        assert user.consent_at is not None
        assert user.consent_policy_version is not None
        assert user.consent_offer_version is not None


class TestParseHelpers:
    def test_parse_phone_text(self):
        from app.modules.maxauth.service import parse_phone_text
        assert parse_phone_text("+7 (999) 123-45-67") == "+7 (999) 123-45-67"
        assert parse_phone_text("89991234567") == "+7 (999) 123-45-67"
        assert parse_phone_text("hello") is None
        assert parse_phone_text("12345") is None

    def test_parse_contact_no_attachment(self):
        from app.modules.maxauth.service import parse_contact_phone
        assert parse_contact_phone({}) == (None, False, "", None)
        assert parse_contact_phone({"body": {}}) == (None, False, "", None)

    def test_parse_vcf_email(self):
        from app.modules.maxauth.service import parse_vcf_email
        vcf = "TEL:79990001122\r\nEMAIL;TYPE=INTERNET:Ivan@Example.COM\r\n"
        assert parse_vcf_email(vcf) == "ivan@example.com"
        assert parse_vcf_email("TEL:79990001122") is None
        assert parse_vcf_email("EMAIL:not-an-email") is None
        assert parse_vcf_email("") is None

    def test_sender_username(self):
        from app.modules.maxauth.service import sender_username
        assert sender_username({"username": "ivan"}) == "ivan"
        assert sender_username({"first_name": "Ivan"}) is None
        assert sender_username({}) is None

    def test_sender_display_name(self):
        from app.modules.maxauth.service import sender_display_name
        assert sender_display_name({"first_name": "A", "last_name": "B"}) == "A B"
        assert sender_display_name({}) == ""

    def test_start_payload_roundtrip(self, max_enabled):
        from app.modules.maxauth.service import (
            make_start_payload, parse_start_payload)
        assert parse_start_payload(make_start_payload(4821)) == 4821
        assert parse_start_payload("garbage") is None
        assert parse_start_payload("") is None
        assert parse_start_payload(make_start_payload(7)[:-1] + "ff") is None

    def test_start_deeplink_shape(self, max_enabled):
        from app.modules.maxauth.service import make_start_deeplink
        link = make_start_deeplink(99)
        assert link.startswith("https://max.ru/test_bot?start=99_")
        assert len(link.split("?start=")[1]) < 128

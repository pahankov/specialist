"""Tests for Yandex ID auth (OAuth 2.0 Authorization Code Flow).

Covers: /yandex/start (signed state + authorize URL, no tokens), /yandex/verify
(state check, code exchange stub, account create/bind, consent), disabled
config, pure helpers. No real Yandex network (YandexAuthApi methods are stubbed).
"""
import pytest

from app.config import settings


@pytest.fixture
def yandex_enabled(monkeypatch):
    monkeypatch.setattr(settings, "YANDEX_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "YANDEX_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setattr(settings, "YANDEX_REDIRECT_URI",
                        "https://site.example/auth/yandex/callback")
    monkeypatch.setattr(settings, "YANDEX_SUGGEST_REDIRECT_URI",
                        "https://site.example/suggest-token.html")
    monkeypatch.setattr(settings, "YANDEX_SCOPE", "")


@pytest.fixture
def no_yandex(monkeypatch):
    monkeypatch.setattr(settings, "YANDEX_CLIENT_ID", "")
    monkeypatch.setattr(settings, "YANDEX_CLIENT_SECRET", "")
    monkeypatch.setattr(settings, "YANDEX_REDIRECT_URI", "")
    monkeypatch.setattr(settings, "YANDEX_SUGGEST_REDIRECT_URI", "")


class _StubYandexApi:
    """Stands in for YandexAuthApi: canned token + profile, records calls."""

    def __init__(self, profile=None, tokens=None, exchange_exc=None,
                 info_exc=None, client_id="test-client-id"):
        self._profile = profile or {}
        self._tokens = tokens or {}
        self._exchange_exc = exchange_exc
        self._info_exc = info_exc
        self._client_id = client_id
        self.exchange_calls = []
        self.info_calls = []
        self.token_calls = []

    async def exchange_code(self, code):
        self.exchange_calls.append({"code": code})
        if self._exchange_exc:
            raise self._exchange_exc
        return self._tokens

    async def token_client_id(self, access_token):
        self.token_calls.append(access_token)
        return self._client_id

    async def user_info(self, access_token):
        self.info_calls.append(access_token)
        if self._info_exc:
            raise self._info_exc
        return self._profile


def _stub(monkeypatch, api):
    import sys
    mod = sys.modules["app.modules.yandexauth.service"]
    monkeypatch.setattr(mod, "get_yandex_api", lambda: api)


def _profile(uid="111", first="Ivan", last="Petrov", email=None):
    p = {"id": uid, "first_name": first, "last_name": last,
         "login": "ivan.login"}
    if email:
        p["default_email"] = email
    return p


def _tokens():
    return {"access_token": "ya-access", "expires_in": 3600,
            "token_type": "bearer"}


async def _start(client):
    resp = await client.post("/api/v1/auth/yandex/start", json={})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _verify(client, start, **over):
    body = {
        "code": "auth-code",
        "state": start["state"],
        "consent": False,
    }
    body.update(over)
    return client.post("/api/v1/auth/yandex/verify", json=body)


class TestYandexStart:
    async def test_start_disabled_without_config(self, client, no_yandex):
        resp = await client.post("/api/v1/auth/yandex/start", json={})
        assert resp.status_code == 503

    async def test_start_returns_authorize_url(self, client, yandex_enabled):
        data = await _start(client)
        url = data["authorize_url"]
        assert url.startswith("https://oauth.yandex.ru/authorize?")
        assert "client_id=test-client-id" in url
        assert "response_type=code" in url
        assert "redirect_uri=" in url
        assert "state=" in url
        assert data["client_id"] == "test-client-id"
        assert data["redirect_uri"] == (
            "https://site.example/auth/yandex/callback")
        assert data["suggest_redirect_uri"] == (
            "https://site.example/suggest-token.html")
        assert data["state"]

    async def test_start_state_is_fresh_and_signed(self, client,
                                                   yandex_enabled):
        from app.modules.yandexauth.service import parse_state
        data = await _start(client)
        assert parse_state(data["state"]) is True


class TestYandexVerify:
    async def test_verify_disabled_without_config(self, client, no_yandex):
        resp = await _verify(client, {"state": "1_x_y"})
        assert resp.status_code == 503

    async def test_verify_rejects_forged_state(self, client, yandex_enabled):
        # A bad state must fail BEFORE any Yandex network call — no stub needed.
        resp = await _verify(client, {"state": "9999999999_deadbeef_0000"})
        assert resp.status_code == 400

    async def test_verify_rejects_tampered_state(self, client, yandex_enabled):
        from app.modules.yandexauth.service import make_state
        state = make_state()
        tampered = state[:-1] + ("0" if state[-1] != "0" else "1")
        resp = await _verify(client, {"state": tampered})
        assert resp.status_code == 400

    async def test_verify_rejects_expired_state(self, client, yandex_enabled,
                                                monkeypatch):
        from app.modules import yandexauth
        # Backdate the TTL so a just-minted state counts as stale.
        monkeypatch.setattr(yandexauth.service, "STATE_TTL_SECONDS", -1)
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 400

    async def test_verify_creates_new_client(self, client, yandex_enabled,
                                             monkeypatch, session):
        api = _StubYandexApi(profile=_profile(email="ivan@ya.example"),
                             tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data, consent=True)
        assert done.status_code == 200
        body = done.json()
        assert body["is_new_user"] is True
        assert body["access_token"]
        # The code was forwarded to the (server-side) exchange.
        assert api.exchange_calls[0]["code"] == "auth-code"

        from sqlalchemy import select
        from app.models.user import User
        user = (await session.execute(
            select(User).where(User.yandex_user_id == 111))).scalar_one()
        assert user.name == "Ivan Petrov"
        assert user.last_name == "Petrov"
        assert user.email == "ivan@ya.example"
        assert user.role.value == "CLIENT"
        assert user.consent_at is not None
        assert user.consent_policy_version

        from app.models.user_contact import UserContact
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == "email"))).scalar_one()
        assert contact.value == "ivan@ya.example"
        assert contact.is_verified is True
        assert contact.verified_via == "social"
        assert contact.is_primary is True

    async def test_verify_attaches_confirmed_phone_contact(
        self, client, yandex_enabled, monkeypatch, session
    ):
        """default_phone is Yandex-confirmed → verified phone contact."""
        from sqlalchemy import select
        from app.models.user import User
        from app.models.user_contact import UserContact

        api = _StubYandexApi(
            profile={**_profile(email="ivan@ya.example"),
                     "default_phone": {"id": "p1",
                                       "number": "+7 916 123-45-67"}},
            tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200

        user = (await session.execute(
            select(User).where(User.yandex_user_id == 111))).scalar_one()
        assert user.phone == "+7 (916) 123-45-67"  # legacy mirror filled
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == "phone"))).scalar_one()
        assert contact.value == "+7 (916) 123-45-67"
        assert contact.is_verified is True
        assert contact.verified_via == "social"
        assert contact.is_primary is True

    async def test_verified_phone_logs_into_existing_account(
        self, client, yandex_enabled, monkeypatch, session
    ):
        """Lookup order: yandex-id → confirmed phone → email → create."""
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.services.contacts import attach_contact

        existing = User(name="Phone Owner", role=UserRole.CLIENT)
        session.add(existing)
        await session.flush()
        contact, _ = await attach_contact(
            session, existing, "phone", "+7 916 123-45-67")
        await session.commit()

        api = _StubYandexApi(
            profile={**_profile(uid="222"),  # a different Yandex id
                     "default_phone": {"id": "p1",
                                       "number": "+79161234567"}},
            tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data, consent=True)
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False

        await session.refresh(existing)
        await session.refresh(contact)
        assert existing.yandex_user_id == 222  # Yandex id got bound
        assert contact.is_verified is True  # confirmed by this very login
        assert contact.verified_via == "social"

    async def test_verify_stamps_no_consent_when_absent(
        self, client, yandex_enabled, monkeypatch, session
    ):
        api = _StubYandexApi(profile=_profile(), tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data, consent=False)
        assert done.status_code == 200

        body = done.json()
        # No consent → a challenge, not a session and not a cookie.
        assert body["challenge"]
        assert body["access_token"] == body["challenge"]
        assert "access_token=" not in done.headers.get("set-cookie", "")

        from sqlalchemy import select
        from app.models.user import User
        user = (await session.execute(
            select(User).where(User.yandex_user_id == 111))).scalar_one()
        assert user.consent_at is None

    async def test_verify_links_existing_email_account(
        self, client, yandex_enabled, monkeypatch, session
    ):
        """Same email as a password account -> bind Yandex, no duplicate."""
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        existing = User(name="Old User", email="ivan@ya.example",
                        hashed_password=hash_password("SecurePass123!"),
                        role=UserRole.CLIENT)
        session.add(existing)
        await session.commit()

        api = _StubYandexApi(profile=_profile(email="ivan@ya.example"),
                             tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False

        await session.refresh(existing)
        assert existing.yandex_user_id == 111

    async def test_verify_existing_yandex_user_is_login(
        self, client, yandex_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        bound = User(name="Bound User", role=UserRole.CLIENT,
                     yandex_user_id=111)
        session.add(bound)
        await session.commit()

        api = _StubYandexApi(profile=_profile(), tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False
        await session.refresh(bound)
        assert bound.name == "Bound User"  # untouched

    async def test_verify_blocked_account_rejected(
        self, client, yandex_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        banned = User(name="Banned", role=UserRole.CLIENT,
                      yandex_user_id=111, is_active=False)
        session.add(banned)
        await session.commit()

        _stub(monkeypatch, _StubYandexApi(profile=_profile(),
                                          tokens=_tokens()))
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 403

    async def test_verify_exchange_failure_is_400(
        self, client, yandex_enabled, monkeypatch
    ):
        from app.services.yandex_api import YandexApiError
        api = _StubYandexApi(exchange_exc=YandexApiError("bad code"))
        _stub(monkeypatch, api)
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 400

    async def test_verify_missing_user_id_is_400(
        self, client, yandex_enabled, monkeypatch
    ):
        # Profile with no id.
        api = _StubYandexApi(profile={"first_name": "X"},
                             tokens={"access_token": "x"})
        _stub(monkeypatch, api)
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 400


class TestYandexSuggestTokenVerify:
    """Widget flow («мгновенная авторизация»): the SDK-delivered access_token
    instead of code + state — same account create/bind tail."""

    async def test_token_verify_creates_new_client(
        self, client, yandex_enabled, monkeypatch, session
    ):
        api = _StubYandexApi(profile=_profile(email="ivan@ya.example"))
        _stub(monkeypatch, api)
        resp = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"access_token": "ya-widget-token", "consent": True},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["is_new_user"] is True
        # client_id is verified first, then the token goes straight to
        # user_info — no code exchange.
        assert api.token_calls == ["ya-widget-token"]
        assert api.info_calls == ["ya-widget-token"]
        assert api.exchange_calls == []

        from sqlalchemy import select
        from app.models.user import User
        from app.models.user_contact import UserContact
        user = (await session.execute(
            select(User).where(User.yandex_user_id == 111))).scalar_one()
        assert user.name == "Ivan Petrov"
        assert user.email == "ivan@ya.example"
        assert user.consent_at is not None
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == "email"))).scalar_one()
        assert contact.verified_via == "social"

    async def test_token_verify_existing_yandex_user_is_login(
        self, client, yandex_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        bound = User(name="Bound User", role=UserRole.CLIENT,
                     yandex_user_id=111)
        session.add(bound)
        await session.commit()

        _stub(monkeypatch, _StubYandexApi(profile=_profile()))
        resp = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"access_token": "ya-widget-token"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_new_user"] is False
        await session.refresh(bound)
        assert bound.name == "Bound User"  # untouched

    async def test_token_verify_rejects_invalid_token(
        self, client, yandex_enabled, monkeypatch
    ):
        from app.services.yandex_api import YandexApiError
        _stub(monkeypatch, _StubYandexApi(info_exc=YandexApiError("revoked")))
        resp = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"access_token": "bad-token"},
        )
        assert resp.status_code == 401

    async def test_token_verify_rejects_foreign_app_token(
        self, client, yandex_enabled, monkeypatch
    ):
        """A token minted for another client_id must never log anyone in."""
        api = _StubYandexApi(profile=_profile(), client_id="other-app")
        _stub(monkeypatch, api)
        resp = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"access_token": "ya-widget-token"},
        )
        assert resp.status_code == 401
        assert api.info_calls == []  # rejected before any profile read

    async def test_token_verify_blocked_account_rejected(
        self, client, yandex_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        banned = User(name="Banned", role=UserRole.CLIENT,
                      yandex_user_id=111, is_active=False)
        session.add(banned)
        await session.commit()

        _stub(monkeypatch, _StubYandexApi(profile=_profile()))
        resp = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"access_token": "ya-widget-token"},
        )
        assert resp.status_code == 403

    async def test_token_verify_disabled_without_config(
        self, client, no_yandex
    ):
        resp = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"access_token": "x"},
        )
        assert resp.status_code == 503

    async def test_verify_requires_exactly_one_flow(
        self, client, yandex_enabled
    ):
        # Neither flow.
        resp = await client.post("/api/v1/auth/yandex/verify", json={})
        assert resp.status_code == 422
        # Both flows at once.
        resp = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"code": "c", "state": "s", "access_token": "t"},
        )
        assert resp.status_code == 422
        # code without its state.
        resp = await client.post(
            "/api/v1/auth/yandex/verify", json={"code": "c"})
        assert resp.status_code == 422

    async def test_start_reports_widget_off_when_unset(
        self, client, yandex_enabled, monkeypatch
    ):
        monkeypatch.setattr(settings, "YANDEX_SUGGEST_REDIRECT_URI", "")
        data = await _start(client)
        assert data["suggest_redirect_uri"] == ""


class TestYandexHelpers:
    def test_make_and_parse_state_roundtrip(self):
        from app.modules.yandexauth.service import make_state, parse_state
        state = make_state()
        assert parse_state(state) is True

    def test_parse_state_rejects_garbage(self):
        from app.modules.yandexauth.service import parse_state
        assert parse_state("") is False
        assert parse_state("no_underscores") is False
        assert parse_state("notanint_x_y") is False
        assert parse_state(None) is False

    def test_parse_state_rejects_wrong_signer(self):
        import hashlib
        import hmac as hmac_mod
        from app.modules.yandexauth.service import parse_state, _state_key
        ts = "1700000000"
        nonce = "abc"
        mac = hmac_mod.new(b"wrong-key", f"{ts}_{nonce}".encode(),
                           hashlib.sha256).hexdigest()[:32]
        assert parse_state(f"{ts}_{nonce}_{mac}") is False

    def test_build_authorize_url_includes_scope_when_set(
        self, yandex_enabled, monkeypatch
    ):
        from app.modules.yandexauth.service import (build_authorize_url,
                                                    make_state)
        monkeypatch.setattr(settings, "YANDEX_SCOPE", "login:info login:email")
        url = build_authorize_url(make_state())
        assert "scope=login%3Ainfo+login%3Aemail" in url

    def test_clean_email(self):
        from app.modules.yandexauth.service import _clean_email
        assert _clean_email("Ivan@Ya.Example ") == "ivan@ya.example"
        assert _clean_email("") is None
        assert _clean_email(None) is None
        assert _clean_email("no-at-sign") is None
        assert _clean_email("has space@x.ru") is None

    def test_clean_phone(self):
        from app.modules.yandexauth.service import _clean_phone
        assert _clean_phone("89161234567") == "+7 (916) 123-45-67"
        assert _clean_phone("+7 916 123-45-67") == "+7 (916) 123-45-67"
        assert _clean_phone("") is None
        assert _clean_phone(None) is None
        assert _clean_phone("not-a-phone") is None


class TestYandexLink:
    """«Привязать Яндекс»: the signed state names the current account."""

    async def test_link_binds_profile_to_current_account(
        self, client, yandex_enabled, monkeypatch, session
    ):
        from sqlalchemy import func, select
        from app.models.user import User, UserRole
        from app.utils.tokens import create_access_token

        me = User(name="Me", role=UserRole.CLIENT)
        session.add(me)
        await session.commit()
        token = create_access_token({
            "sub": str(me.id), "role": me.role.value, "name": me.name,
        })

        _stub(monkeypatch, _StubYandexApi(
            profile=_profile(email="me@ya.example"), tokens=_tokens()))
        start = await client.post(
            "/api/v1/auth/yandex/start",
            json={"link": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert start.status_code == 200

        done = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"code": "auth-code", "state": start.json()["state"]},
        )
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False

        await session.refresh(me)
        assert me.yandex_user_id == 111  # bound to ME, not a new account
        assert me.email == "me@ya.example"
        total = (await session.execute(
            select(func.count()).select_from(User))).scalar_one()
        assert total == 1  # no account was forked

    async def test_link_requires_auth(self, client, yandex_enabled):
        resp = await client.post("/api/v1/auth/yandex/start",
                                 json={"link": True})
        assert resp.status_code == 401

    async def test_link_conflict_when_yandex_bound_elsewhere(
        self, client, yandex_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        from app.utils.tokens import create_access_token

        other = User(name="Other", role=UserRole.CLIENT, yandex_user_id=111)
        me = User(name="Me", role=UserRole.CLIENT)
        session.add_all([other, me])
        await session.commit()
        token = create_access_token({
            "sub": str(me.id), "role": me.role.value, "name": me.name,
        })

        _stub(monkeypatch, _StubYandexApi(
            profile=_profile(), tokens=_tokens()))
        start = await client.post(
            "/api/v1/auth/yandex/start",
            json={"link": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert start.status_code == 200
        done = await client.post(
            "/api/v1/auth/yandex/verify",
            json={"code": "auth-code", "state": start.json()["state"]},
        )
        assert done.status_code == 409

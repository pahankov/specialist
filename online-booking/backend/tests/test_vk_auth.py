"""Tests for VK ID auth (OAuth 2.0 Authorization Code Flow + PKCE).

Covers: /vk/start (signed state + authorize URL, no tokens), /vk/verify
(state check, code exchange stub, account create/bind, consent), disabled
state, pure helpers. No real VK network (VkAuthApi methods are stubbed).
"""
import pytest

from app.config import settings


# A syntactically valid PKCE challenge (BASE64URL of SHA256, 43 chars).
CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"
VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"


@pytest.fixture
def vk_enabled(monkeypatch):
    monkeypatch.setattr(settings, "VK_CLIENT_ID", "test-client-id")
    monkeypatch.setattr(settings, "VK_SERVICE_TOKEN", "test-service-token")
    monkeypatch.setattr(settings, "VK_REDIRECT_URI",
                        "https://site.example/auth/vk/callback")
    monkeypatch.setattr(settings, "VK_SCOPE", "")


@pytest.fixture
def no_vk(monkeypatch):
    monkeypatch.setattr(settings, "VK_CLIENT_ID", "")
    monkeypatch.setattr(settings, "VK_REDIRECT_URI", "")


class _StubVkApi:
    """Stands in for VkAuthApi: canned token + profile, records calls."""

    def __init__(self, profile=None, tokens=None, exchange_exc=None,
                 info_exc=None):
        self._profile = profile or {}
        self._tokens = tokens or {}
        self._exchange_exc = exchange_exc
        self._info_exc = info_exc
        self.exchange_calls = []
        self.info_calls = []

    async def exchange_code(self, code, code_verifier, device_id, state):
        self.exchange_calls.append(
            {"code": code, "code_verifier": code_verifier,
             "device_id": device_id, "state": state})
        if self._exchange_exc:
            raise self._exchange_exc
        return self._tokens

    async def user_info(self, access_token):
        self.info_calls.append(access_token)
        if self._info_exc:
            raise self._info_exc
        return self._profile


def _stub(monkeypatch, api):
    import sys
    mod = sys.modules["app.modules.vkauth.service"]
    monkeypatch.setattr(mod, "get_vk_api", lambda: api)


def _profile(user_id=111, first="Ivan", last="Petrov", email=None,
             verified=True):
    user = {"user_id": user_id, "first_name": first, "last_name": last,
            "verified": verified}
    if email:
        user["email"] = email
    return {"user": user}


def _tokens(user_id=111):
    return {"access_token": "vk-access", "refresh_token": "vk-refresh",
            "id_token": "vk-id", "user_id": user_id, "token_type": "Bearer"}


async def _start(client):
    resp = await client.post("/api/v1/auth/vk/start",
                             json={"code_challenge": CHALLENGE})
    assert resp.status_code == 200, resp.text
    return resp.json()


def _verify(client, start, **over):
    body = {
        "code": "auth-code",
        "device_id": "dev-123",
        "state": start["state"],
        "code_verifier": VERIFIER,
        "consent": False,
    }
    body.update(over)
    return client.post("/api/v1/auth/vk/verify", json=body)


class TestVkStart:
    async def test_start_disabled_without_config(self, client, no_vk):
        resp = await client.post("/api/v1/auth/vk/start",
                                 json={"code_challenge": CHALLENGE})
        assert resp.status_code == 503

    async def test_start_returns_authorize_url(self, client, vk_enabled):
        data = await _start(client)
        url = data["authorize_url"]
        assert url.startswith("https://id.vk.ru/authorize?")
        assert "client_id=test-client-id" in url
        assert "response_type=code" in url
        assert "code_challenge_method=S256" in url
        assert f"code_challenge={CHALLENGE}" in url
        assert "redirect_uri=" in url
        assert data["client_id"] == "test-client-id"
        assert data["state"]

    async def test_start_state_is_fresh_and_signed(self, client, vk_enabled):
        from app.modules.vkauth.service import parse_state
        data = await _start(client)
        assert parse_state(data["state"]) is True

    async def test_start_rejects_short_challenge(self, client, vk_enabled):
        resp = await client.post("/api/v1/auth/vk/start",
                                 json={"code_challenge": "short"})
        assert resp.status_code == 422


class TestVkVerify:
    async def test_verify_disabled_without_config(self, client, no_vk):
        resp = await _verify(client, {"state": "1_x_y"})
        assert resp.status_code == 503

    async def test_verify_rejects_forged_state(self, client, vk_enabled):
        # A bad state must fail BEFORE any VK network call — no stub needed.
        resp = await _verify(client, {"state": "9999999999_deadbeef_0000"})
        assert resp.status_code == 400

    async def test_verify_rejects_tampered_state(self, client, vk_enabled):
        from app.modules.vkauth.service import make_state
        state = make_state()
        tampered = state[:-1] + ("0" if state[-1] != "0" else "1")
        resp = await _verify(client, {"state": tampered})
        assert resp.status_code == 400

    async def test_verify_rejects_expired_state(self, client, vk_enabled,
                                                monkeypatch):
        from app.modules import vkauth
        # Backdate the TTL so a just-minted state counts as stale.
        monkeypatch.setattr(vkauth.service, "STATE_TTL_SECONDS", -1)
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 400

    async def test_verify_creates_new_client(self, client, vk_enabled,
                                             monkeypatch, session):
        api = _StubVkApi(profile=_profile(email="ivan@vk.example"),
                         tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data, consent=True)
        assert done.status_code == 200
        body = done.json()
        assert body["is_new_user"] is True
        assert body["access_token"]
        # PKCE verifier was forwarded to the exchange.
        assert api.exchange_calls[0]["code_verifier"] == VERIFIER
        assert api.exchange_calls[0]["state"] == data["state"]

        from sqlalchemy import select
        from app.models.user import User
        user = (await session.execute(
            select(User).where(User.vk_user_id == 111))).scalar_one()
        assert user.name == "Ivan Petrov"
        assert user.last_name == "Petrov"
        assert user.email == "ivan@vk.example"
        assert user.role.value == "CLIENT"
        assert user.is_verified is True
        assert user.consent_at is not None
        assert user.consent_policy_version

    async def test_verify_stamps_no_consent_when_absent(
        self, client, vk_enabled, monkeypatch, session
    ):
        api = _StubVkApi(profile=_profile(), tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data, consent=False)
        assert done.status_code == 200

        from sqlalchemy import select
        from app.models.user import User
        user = (await session.execute(
            select(User).where(User.vk_user_id == 111))).scalar_one()
        assert user.consent_at is None

    async def test_verify_links_existing_email_account(
        self, client, vk_enabled, monkeypatch, session
    ):
        """Same email as a password account -> bind VK, no duplicate."""
        from app.models.user import User, UserRole
        from app.utils.security import hash_password
        existing = User(name="Old User", email="ivan@vk.example",
                        hashed_password=hash_password("SecurePass123!"),
                        role=UserRole.CLIENT)
        session.add(existing)
        await session.commit()

        api = _StubVkApi(profile=_profile(email="ivan@vk.example"),
                         tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False

        await session.refresh(existing)
        assert existing.vk_user_id == 111

    async def test_verify_existing_vk_user_is_login(
        self, client, vk_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        bound = User(name="Bound User", role=UserRole.CLIENT, vk_user_id=111)
        session.add(bound)
        await session.commit()

        api = _StubVkApi(profile=_profile(), tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False
        await session.refresh(bound)
        assert bound.name == "Bound User"  # untouched

    async def test_verify_blocked_account_rejected(
        self, client, vk_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        banned = User(name="Banned", role=UserRole.CLIENT, vk_user_id=111,
                      is_active=False)
        session.add(banned)
        await session.commit()

        _stub(monkeypatch, _StubVkApi(profile=_profile(), tokens=_tokens()))
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 403

    async def test_verify_exchange_failure_is_400(
        self, client, vk_enabled, monkeypatch
    ):
        from app.services.vk_api import VkApiError
        api = _StubVkApi(exchange_exc=VkApiError("bad code"))
        _stub(monkeypatch, api)
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 400

    async def test_verify_missing_vk_user_id_is_400(
        self, client, vk_enabled, monkeypatch
    ):
        # Profile with no user_id and no token user_id.
        api = _StubVkApi(profile={"user": {}}, tokens={"access_token": "x"})
        _stub(monkeypatch, api)
        data = await _start(client)
        resp = await _verify(client, data)
        assert resp.status_code == 400


class TestVkHelpers:
    def test_make_and_parse_state_roundtrip(self):
        from app.modules.vkauth.service import make_state, parse_state
        state = make_state()
        assert parse_state(state) is True

    def test_parse_state_rejects_garbage(self):
        from app.modules.vkauth.service import parse_state
        assert parse_state("") is False
        assert parse_state("no_underscores") is False
        assert parse_state("notanint_x_y") is False
        assert parse_state(None) is False

    def test_parse_state_rejects_wrong_signer(self):
        import hashlib
        import hmac as hmac_mod
        from app.modules.vkauth.service import parse_state, _state_key
        # Correctly-shaped but signed with a foreign key.
        ts = "1700000000"
        nonce = "abc"
        mac = hmac_mod.new(b"wrong-key", f"{ts}_{nonce}".encode(),
                           hashlib.sha256).hexdigest()[:32]
        assert parse_state(f"{ts}_{nonce}_{mac}") is False

    def test_build_authorize_url_includes_scope_when_set(
        self, vk_enabled, monkeypatch
    ):
        from app.modules.vkauth.service import build_authorize_url, make_state
        monkeypatch.setattr(settings, "VK_SCOPE", "email phone")
        url = build_authorize_url(make_state(), CHALLENGE)
        assert "scope=email+phone" in url

    def test_clean_email(self):
        from app.modules.vkauth.service import _clean_email
        assert _clean_email("Ivan@VK.Example ") == "ivan@vk.example"
        assert _clean_email("") is None
        assert _clean_email(None) is None
        assert _clean_email("no-at-sign") is None
        assert _clean_email("has space@x.ru") is None

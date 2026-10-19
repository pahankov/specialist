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
             verified=True, avatar=None):
    user = {"user_id": user_id, "first_name": first, "last_name": last,
            "verified": verified}
    if email:
        user["email"] = email
    if avatar:
        user["avatar"] = avatar
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
        assert user.consent_at is not None
        assert user.consent_policy_version

        from app.models.user_contact import UserContact
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.user_id == user.id,
                UserContact.contact_type == "email"))).scalar_one()
        assert contact.value == "ivan@vk.example"
        assert contact.is_verified is True
        assert contact.verified_via == "social"
        assert contact.is_primary is True

    async def test_verify_stamps_no_consent_when_absent(
        self, client, vk_enabled, monkeypatch, session
    ):
        api = _StubVkApi(profile=_profile(), tokens=_tokens())
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
            select(User).where(User.vk_user_id == 111))).scalar_one()
        assert user.consent_at is None

    async def test_pending_account_asks_consent_again(
        self, client, vk_enabled, monkeypatch, session
    ):
        """An abandoned registration must not log in on the next attempt."""
        api = _StubVkApi(profile=_profile(), tokens=_tokens())
        _stub(monkeypatch, api)
        first = await _verify(client, await _start(client), consent=False)
        assert first.json()["challenge"]

        second = await _verify(client, await _start(client), consent=False)
        assert second.status_code == 200
        body = second.json()
        assert body["challenge"]  # still pending — ask for consent again
        assert body["is_new_user"] is False  # same account was found
        assert "access_token=" not in second.headers.get("set-cookie", "")

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


class TestVkProfileSync:
    """Smart merge of a VK profile into a created/existing account.

    Policy under test: a new account stores the VK avatar + marks the name as
    VK-set; a re-login refreshes VK-set name/avatar; a human-edited name is
    never overwritten; is_verified only goes up; email fills only when empty
    and free.
    """

    async def test_new_user_gets_avatar_and_name_source(
        self, client, vk_enabled, monkeypatch, session
    ):
        api = _StubVkApi(
            profile=_profile(email="ivan@vk.example",
                             avatar="https://vk.example/photo.png"),
            tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data, consent=True)
        assert done.status_code == 200

        from sqlalchemy import select
        from app.models.user import User
        user = (await session.execute(
            select(User).where(User.vk_user_id == 111))).scalar_one()
        assert user.avatar_url == "https://vk.example/photo.png"
        assert user.name_source == "vk"

    async def test_relogin_refreshes_vk_set_name_and_avatar(
        self, client, vk_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        bound = User(name="Ivan Petrov", last_name="Petrov",
                     role=UserRole.CLIENT, vk_user_id=111, name_source="vk")
        session.add(bound)
        await session.commit()

        api = _StubVkApi(
            profile=_profile(first="Petr", last="Ivanov",
                             avatar="https://vk.example/new.png"),
            tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200

        await session.refresh(bound)
        assert bound.name == "Petr Ivanov"  # latest VK login wins
        assert bound.last_name == "Ivanov"
        assert bound.avatar_url == "https://vk.example/new.png"
        assert bound.name_source == "vk"

    async def test_relogin_never_overwrites_human_edited_name(
        self, client, vk_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        bound = User(name="Своё Имя", last_name="Фамилия",
                     role=UserRole.CLIENT, vk_user_id=111, name_source="user")
        session.add(bound)
        await session.commit()

        api = _StubVkApi(profile=_profile(first="Ivan", last="Petrov"),
                         tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200

        await session.refresh(bound)
        assert bound.name == "Своё Имя"  # untouched
        assert bound.name_source == "user"

    async def test_confirmed_email_upgrades_unverified_contact(
        self, client, vk_enabled, monkeypatch, session
    ):
        """A contact is upgraded (never downgraded) by a social vouch."""
        from app.models.user import User, UserRole
        from app.services.contacts import attach_contact

        bound = User(name="Proved", role=UserRole.CLIENT, vk_user_id=111,
                     name_source="user")
        session.add(bound)
        await session.flush()
        contact, _ = await attach_contact(
            session, bound, "email", "proved@vk.example")
        await session.commit()
        assert contact.is_verified is False

        api = _StubVkApi(profile=_profile(email="proved@vk.example"),
                         tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200

        await session.refresh(contact)
        assert contact.is_verified is True
        assert contact.verified_via == "social"

    async def test_email_fills_when_empty_and_free(
        self, client, vk_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole
        bound = User(name="No Email", role=UserRole.CLIENT, vk_user_id=111,
                     name_source="user")
        session.add(bound)
        await session.commit()

        api = _StubVkApi(profile=_profile(email="fresh@vk.example"),
                         tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200

        await session.refresh(bound)
        assert bound.email == "fresh@vk.example"  # legacy mirror filled

        from sqlalchemy import select
        from app.models.user_contact import UserContact
        contact = (await session.execute(
            select(UserContact).where(
                UserContact.user_id == bound.id,
                UserContact.contact_type == "email"))).scalar_one()
        assert contact.value == "fresh@vk.example"
        assert contact.verified_via == "social"

    async def test_confirmed_email_transfers_from_another_account(
        self, client, vk_enabled, monkeypatch, session
    ):
        """Provider-confirmed email moves to the VK account (audit-logged)."""
        from sqlalchemy import select
        from app.models.user import User, UserRole
        from app.models.user_contact import UserContact
        from app.services.contacts import attach_contact

        owner = User(name="Owner", email="busy@vk.example",
                     role=UserRole.CLIENT)
        bound = User(name="No Email", role=UserRole.CLIENT, vk_user_id=111,
                     name_source="user")
        session.add_all([owner, bound])
        await session.flush()
        await attach_contact(session, owner, "email", "busy@vk.example")
        await session.commit()

        api = _StubVkApi(profile=_profile(email="busy@vk.example"),
                         tokens=_tokens())
        _stub(monkeypatch, api)
        data = await _start(client)
        done = await _verify(client, data)
        assert done.status_code == 200

        contact = (await session.execute(
            select(UserContact).where(
                UserContact.contact_type == "email",
                UserContact.value == "busy@vk.example"))).scalar_one()
        assert contact.user_id == bound.id  # moved to the VK account
        assert contact.verified_via == "social"
        await session.refresh(owner)
        await session.refresh(bound)
        assert owner.email is None  # donor's legacy mirror cleared
        assert bound.email == "busy@vk.example"


class TestVkLink:
    """«Привязать VK»: the signed state names the current account."""

    async def _token_for(self, user):
        from app.utils.tokens import create_access_token
        return create_access_token({
            "sub": str(user.id), "role": user.role.value, "name": user.name,
        })

    async def test_link_binds_profile_to_current_account(
        self, client, vk_enabled, monkeypatch, session
    ):
        from sqlalchemy import func, select
        from app.models.user import User, UserRole

        me = User(name="Me", role=UserRole.CLIENT)
        session.add(me)
        await session.commit()
        token = await self._token_for(me)

        api = _StubVkApi(profile=_profile(email="me@vk.example"),
                         tokens=_tokens())
        _stub(monkeypatch, api)
        start = await client.post(
            "/api/v1/auth/vk/start",
            json={"code_challenge": CHALLENGE, "link": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert start.status_code == 200

        done = await _verify(client, start.json())
        assert done.status_code == 200
        assert done.json()["is_new_user"] is False

        await session.refresh(me)
        assert me.vk_user_id == 111  # bound to ME, not a new account
        assert me.email == "me@vk.example"
        total = (await session.execute(
            select(func.count()).select_from(User))).scalar_one()
        assert total == 1  # no account was forked

    async def test_link_requires_auth(self, client, vk_enabled):
        resp = await client.post(
            "/api/v1/auth/vk/start",
            json={"code_challenge": CHALLENGE, "link": True},
        )
        assert resp.status_code == 401

    async def test_link_conflict_when_vk_bound_elsewhere(
        self, client, vk_enabled, monkeypatch, session
    ):
        from app.models.user import User, UserRole

        other = User(name="Other", role=UserRole.CLIENT, vk_user_id=111)
        me = User(name="Me", role=UserRole.CLIENT)
        session.add_all([other, me])
        await session.commit()
        token = await self._token_for(me)

        _stub(monkeypatch, _StubVkApi(profile=_profile(), tokens=_tokens()))
        start = await client.post(
            "/api/v1/auth/vk/start",
            json={"code_challenge": CHALLENGE, "link": True},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert start.status_code == 200
        done = await _verify(client, start.json())
        assert done.status_code == 409

    async def test_link_state_uid_is_tamper_proof(self):
        from app.modules.vkauth.service import make_state, _parse_state
        state = make_state(link_user_id=42)
        ok, uid = _parse_state(state)
        assert ok is True and uid == 42
        # Swap the uid — the MAC must break.
        parts = state.split("_")
        parts[2] = "43"
        assert _parse_state("_".join(parts))[0] is False

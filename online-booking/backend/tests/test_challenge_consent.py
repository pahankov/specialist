"""Tests for the 2-step challenge/consent flow (152-FZ, 1.80.0).

Covers two flows:
1. Phone register: /phone/status → challenge → /register-unified with challenge
2. OAuth verify: /vk/verify (or /yandex/verify) → challenge → /consent/complete

The challenge token is a signed JWT with {sub: user_id, phone, iat}.
For phone/status: user_id=0 (user doesn't exist yet).
For OAuth verify: user_id points to a pending user (created but not committed).
"""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.user import User
from sqlalchemy import select


@pytest.fixture
async def client():
    """Test client with clean DB."""
    from app.database import AsyncSessionLocal
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ─── POST /api/v1/auth/phone/status ──────────────────────────────────


class TestPhoneStatusChallenge:
    """phone/status must return challenge for new accounts."""

    async def test_new_phone_returns_challenge(self, client):
        """New phone → state='new' + challenge token."""
        resp = await client.post(
            "/api/v1/auth/phone/status",
            json={"phone": "+7 (999) 111-22-33"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "new"
        assert data["phone"] == "+7 (999) 111-22-33"
        assert "challenge" in data
        assert data["challenge"]  # non-empty string


# ─── POST /api/v1/auth/register-unified with challenge ──────────────


class TestRegisterUnifiedWithChallenge:
    """register-unified must accept challenge instead of phone."""

    async def test_register_with_challenge_creates_session(self, client):
        """Challenge from phone/status → account created with consent."""
        import time
        phone = f"+7 (999) {int(time.time()) % 1000:03d}-66-77"
        # Step 1: Get challenge
        status_resp = await client.post(
            "/api/v1/auth/phone/status",
            json={"phone": phone},
        )
        challenge = status_resp.json()["challenge"]

        # Step 2: Register with challenge
        register_resp = await client.post(
            "/api/v1/auth/register-unified",
            json={
                "challenge": challenge,
                "password": "SecurePass1!",
                "consent": True,
            },
        )
        assert register_resp.status_code == 201
        data = register_resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Verify account exists with consent
        from app.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(User).where(User.phone == phone)
            )
            user = result.scalar_one_or_none()
            assert user is not None
            assert user.consent_at is not None
            assert user.consent_policy_version is not None
            assert user.is_active is True

    async def test_register_with_challenge_rejects_invalid_token(self, client):
        """Invalid challenge → 400."""
        resp = await client.post(
            "/api/v1/auth/register-unified",
            json={
                "challenge": "invalid_token_xyz",
                "password": "SecurePass1!",
                "consent": True,
            },
        )
        assert resp.status_code == 400


# ─── POST /api/v1/auth/consent/complete ──────────────────────────────


class TestConsentComplete:
    """consent/complete must stamp consent for pending OAuth users."""
    async def test_complete_consent_rejects_orphan_challenge(self, client):
        """Challenge from phone/status (user_id=0) → 400 (user not found).

        consent/complete is designed for OAuth verify challenges where
        the user was already created (but not committed) during verify.
        Phone/status challenges must use register-unified instead.
        """
        # Get challenge from phone/status
        status_resp = await client.post(
            "/api/v1/auth/phone/status",
            json={"phone": "+7 (999) 777-88-99"},
        )
        challenge = status_resp.json()["challenge"]

        # Try to complete with consent/complete → should fail (user_id=0)
        resp = await client.post(
            "/api/v1/auth/consent/complete",
            json={"challenge": challenge, "consent": True},
        )
        assert resp.status_code == 400

    async def test_complete_consent_rejects_invalid_token(self, client):
        """Invalid JWT → 400."""
        resp = await client.post(
            "/api/v1/auth/consent/complete",
            json={"challenge": "invalid_token_xyz", "consent": True},
        )
        assert resp.status_code == 400


# ─── Challenge token internals ──────────────────────────────────────


class TestChallengeToken:
    """The challenge is a 5-minute quasi-session — its TTL must be enforced
    and the routers must be able to tell it apart from a session JWT."""

    def test_challenge_ttl_is_enforced(self):
        from datetime import datetime, timedelta, timezone

        import jwt
        from fastapi import HTTPException

        from app.modules.auth.service import (
            ALGORITHM,
            CHALLENGE_TTL_SECONDS,
            SECRET_KEY,
            _decode_challenge_token,
        )

        issued = datetime.now(timezone.utc) - timedelta(
            seconds=CHALLENGE_TTL_SECONDS + 30)
        token = jwt.encode(
            {"sub": "1", "phone": "", "iat": issued},
            SECRET_KEY, algorithm=ALGORITHM,
        )
        with pytest.raises(HTTPException) as exc:
            _decode_challenge_token(token)
        assert exc.value.status_code == 400

    def test_challenge_is_detected(self):
        from app.modules.auth.service import (
            _create_challenge_token,
            is_challenge_token,
        )

        challenge = _create_challenge_token(5, "+7 (999) 000-11-22")
        assert is_challenge_token(challenge) is True
        # A session JWT is not a challenge.
        from app.utils.tokens import create_access_token

        session = create_access_token(
            {"sub": "5", "role": "CLIENT", "name": "", "is_admin": False})
        assert is_challenge_token(session) is False
        assert is_challenge_token("") is False
        assert is_challenge_token("not-a-jwt") is False

"""Unit tests for JWT token creation and validation.

Covers:
- create_access_token — generates valid JWT with user_id, role, expiry
- create_refresh_token_payload — generates refresh token with user_id, email
- Token structure validation
"""
import pytest
from datetime import timedelta


class TestCreateAccessToken:
    """Tests for create_access_token function."""

    def test_token_contains_user_id(self):
        """Access token payload contains user ID."""
        from app.modules.auth.token import create_access_token
        from jose import jwt
        from app.config import settings

        token = create_access_token({"sub": "42", "role": "MASTER"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "42"

    def test_token_contains_role(self):
        """Access token payload contains role."""
        from app.modules.auth.token import create_access_token
        from jose import jwt
        from app.config import settings

        token = create_access_token({"sub": "1", "role": "ADMIN"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["role"] == "ADMIN"

    def test_token_expiry_is_correct(self):
        """Access token has expiry within expected range."""
        from app.modules.auth.token import create_access_token
        from jose import jwt
        from app.config import settings
        from datetime import datetime, timezone as dt_timezone

        expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        token = create_access_token({"sub": "1", "role": "MASTER"})
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

        exp = payload["exp"]
        now = datetime.now(dt_timezone.utc).timestamp()
        diff_minutes = (exp - now) / 60

        # Expiry should be close to ACCESS_TOKEN_EXPIRE_MINUTES
        assert abs(diff_minutes - expire_minutes) < 5

    def test_token_contains_extra_fields(self):
        """Access token preserves extra fields from payload."""
        from app.modules.auth.token import create_access_token
        from jose import jwt
        from app.config import settings

        token = create_access_token({
            "sub": "1",
            "role": "MASTER",
            "name": "Test User",
            "is_admin": False
        })
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["name"] == "Test User"
        assert payload["is_admin"] is False

    def test_token_is_valid_jwt(self):
        """Generated token is a valid JWT that can be decoded."""
        from app.modules.auth.token import create_access_token
        from jose import jwt
        from app.config import settings

        token = create_access_token({"sub": "1", "role": "MASTER"})
        # Should not raise
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload
        assert "sub" in payload


class TestCreateRefreshTokenPayload:
    """Tests for create_refresh_token_payload function."""

    def test_payload_has_user_id(self):
        """Refresh token payload contains user ID."""
        from app.modules.auth.token import create_refresh_token_payload
        from jose import jwt
        from app.config import settings

        token, _ = create_refresh_token_payload(42, "test@example.com")
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["sub"] == "42"

    def test_payload_has_email(self):
        """Refresh token payload contains email."""
        from app.modules.auth.token import create_refresh_token_payload
        from jose import jwt
        from app.config import settings

        token, _ = create_refresh_token_payload(1, "user@example.com")
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["email"] == "user@example.com"

    def test_payload_has_expires_at(self):
        """Refresh token payload has expiry."""
        from app.modules.auth.token import create_refresh_token_payload
        from jose import jwt
        from app.config import settings

        token, expires_at = create_refresh_token_payload(1, "test@example.com")
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "exp" in payload
        # JWT exp is integer seconds, datetime.timestamp() returns float
        assert payload["exp"] == int(expires_at.timestamp())

    def test_payload_has_type(self):
        """Refresh token payload has type='refresh'."""
        from app.modules.auth.token import create_refresh_token_payload
        from jose import jwt
        from app.config import settings

        token, _ = create_refresh_token_payload(1, "test@example.com")
        payload = jwt.decode(token, settings.REFRESH_SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert payload["type"] == "refresh"

    def test_payload_has_jti(self):
        """Refresh token payload has unique JTI."""
        from app.modules.auth.token import create_refresh_token_payload

        token1, _ = create_refresh_token_payload(1, "test@example.com")
        token2, _ = create_refresh_token_payload(1, "test@example.com")
        assert token1 != token2  # Different JTI produces different tokens


class TestTokenSecurity:
    """Tests for token security properties."""

    def test_different_secrets_for_access_and_refresh(self):
        """Access and refresh tokens use different secrets."""
        from app.modules.auth.token import create_access_token, create_refresh_token_payload
        from jose import jwt, JWTError
        from app.config import settings

        access_token = create_access_token({"sub": "1", "role": "MASTER"})
        refresh_token, _ = create_refresh_token_payload(1, "test@example.com")

        # Access token should decode with SECRET_KEY
        payload = jwt.decode(
            access_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        assert payload["sub"] == "1"

        # Refresh token should NOT decode with SECRET_KEY (different secret)
        with pytest.raises(JWTError):
            jwt.decode(
                refresh_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )

    def test_token_expires_with_custom_delta(self):
        """Access token respects custom expires_delta."""
        from app.modules.auth.token import create_access_token
        from jose import jwt
        from app.config import settings
        from datetime import datetime, timezone as dt_timezone

        token = create_access_token(
            {"sub": "1", "role": "MASTER"},
            expires_delta=timedelta(minutes=5)
        )
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = payload["exp"]
        now = datetime.now(dt_timezone.utc).timestamp()
        diff_minutes = (exp - now) / 60
        assert abs(diff_minutes - 5) < 1

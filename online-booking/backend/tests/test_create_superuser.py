"""Tests for create_superuser.ensure_superuser (routine deploys must not
reset the production password when SUPERUSER_PASSWORD is absent)."""
import pytest

from app.models.user import User, UserRole
from app.utils.security import verify_password
from create_superuser import ensure_superuser


async def _make_user(session, email="admin@example.com", password="OrigPass123!"):
    from app.utils.security import hash_password
    user = User(
        name="Admin",
        email=email,
        hashed_password=hash_password(password),
        phone="+70000000000",
        role=UserRole.MASTER,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


class TestEnsureSuperuser:
    async def test_existing_user_keeps_password_without_env(self, session):
        """Deploy without SUPERUSER_PASSWORD: hash untouched, role ensured."""
        user = await _make_user(session)
        old_hash = user.hashed_password

        updated = await ensure_superuser(session, user.email, None)

        assert updated.role == UserRole.ADMIN
        assert updated.is_active is True
        assert updated.hashed_password == old_hash
        assert verify_password("OrigPass123!", updated.hashed_password) is True

    async def test_existing_user_rotates_password_with_env(self, session):
        """SUPERUSER_PASSWORD set: hash rotated to the new value."""
        user = await _make_user(session)

        updated = await ensure_superuser(session, user.email, "BrandNew456!")

        assert updated.role == UserRole.ADMIN
        assert verify_password("BrandNew456!", updated.hashed_password) is True
        assert verify_password("OrigPass123!", updated.hashed_password) is False

    async def test_missing_user_without_password_fails(self, session):
        """No user + no password: fail fast instead of a broken account."""
        with pytest.raises(SystemExit):
            await ensure_superuser(session, "nobody@example.com", None)

    async def test_missing_user_with_password_creates_admin(self, session):
        """No user + password: creates an active verified ADMIN."""
        created = await ensure_superuser(session, "newadmin@example.com", "SomePass789!")

        assert created.role == UserRole.ADMIN
        assert created.is_active is True
        assert created.is_verified is True
        assert verify_password("SomePass789!", created.hashed_password) is True

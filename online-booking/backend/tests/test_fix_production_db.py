"""Tests for fix_production_db.fix_superuser (must not reset prod password)."""
from app.models.user import User, UserRole
from app.utils.security import hash_password, verify_password
from fix_production_db import fix_superuser


async def _make_user(session, email="fixadmin@example.com"):
    user = User(
        name="Admin",
        email=email,
        hashed_password=hash_password("KeepMe123!"),
        phone="+70000000001",
        role=UserRole.MASTER,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    return user


class TestFixSuperuser:
    async def test_existing_user_keeps_password_without_env(self, session):
        """Routine deploy without password: hash untouched, role ensured."""
        user = await _make_user(session)
        old_hash = user.hashed_password

        updated = await fix_superuser(session, user.email, None)

        assert updated.role == UserRole.ADMIN
        assert updated.hashed_password == old_hash
        assert verify_password("KeepMe123!", updated.hashed_password) is True

    async def test_existing_user_rotates_password_with_env(self, session):
        """Password given: hash rotated."""
        user = await _make_user(session)

        updated = await fix_superuser(session, user.email, "Rotated456!")

        assert updated.role == UserRole.ADMIN
        assert verify_password("Rotated456!", updated.hashed_password) is True

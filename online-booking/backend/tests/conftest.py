"""
Pytest configuration for Online Booking backend tests.
"""
import os

# Rate limiting must be disabled BEFORE app import (rate_limit reads env at import).
# CI sets RATE_LIMIT_DISABLED=true explicitly; setdefault keeps local runs safe too.
os.environ.setdefault("RATE_LIMIT_DISABLED", "true")

import pytest
import tempfile
import uuid
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.database import Base, get_db

# When set, run the suite against real PostgreSQL (CI job). Without it every
# test gets a throwaway SQLite file, which hides PG-specific behavior.
PG_TEST_URL = os.getenv("TEST_DATABASE_URL", "").strip()


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create an isolated test database for each test.

    PostgreSQL mode drops/recreates the schema objects so tests see a clean
    database without relying on SQLite semantics.
    """
    if PG_TEST_URL:
        engine = create_async_engine(PG_TEST_URL, echo=False, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()
        return

    db_file = tempfile.mktemp(suffix=f"_{uuid.uuid4().hex[:8]}.db")
    db_url = f"sqlite+aiosqlite:///{db_file}"

    engine = create_async_engine(db_url, echo=False)
    # Use connect() instead of begin() to avoid transaction issues with DDL
    async with engine.connect() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.commit()
    yield engine
    await engine.dispose()
    if os.path.exists(db_file):
        os.remove(db_file)


@pytest_asyncio.fixture(scope="function")
async def session(engine) -> AsyncSession:
    """Create a new session — commits changes for test visibility."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s
        await s.commit()  # Commit so data is visible within the test


# ─── HTTP Client Fixture ─────────────────────────────────────────────

@pytest_asyncio.fixture(scope="function")
async def client(session):
    """Override DB dependency and create test HTTP client."""
    async def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ─── Auth Helper Fixtures ────────────────────────────────────────────

@pytest.fixture
def test_master_data():
    """Valid master registration data."""
    return {
        "name": "Test Master",
        "email": "test_master@example.com",
        "password": "SecurePass123!",
        "phone": "+79990001122",
        "telegram_username": "test_master",
        "role": "MASTER",
    }


def master_access_token(user) -> str:
    """Mint a MASTER JWT directly — password login is social-only (1.83.0)."""
    from app.modules.auth.token import create_access_token

    return create_access_token({
        "sub": str(user.id),
        "role": user.role.value,
        "name": user.name,
        "last_name": user.last_name,
        "is_admin": False,
    })


async def issue_master_refresh(session, user) -> str:
    """Store a valid refresh token for a master without a password login."""
    from app.models.refresh_token import RefreshToken
    from app.utils.tokens import create_refresh_token_payload

    token, expires_at = create_refresh_token_payload(user.id, user.email or "")
    session.add(RefreshToken(
        user_id=user.id, token=token, expires_at=expires_at, is_revoked=False,
    ))
    await session.commit()
    return token


@pytest.fixture
async def auth_token(client, session, test_master_data):
    """Register a master and return a directly minted JWT token."""
    from sqlalchemy import select
    from app.models.user import User

    resp = await client.post("/api/v1/auth/register", json=test_master_data)
    assert resp.status_code == 201, f"Register failed: {resp.text}"
    user = (await session.execute(
        select(User).where(User.email == test_master_data["email"])
    )).scalar_one()
    return master_access_token(user)


@pytest.fixture
def auth_headers(auth_token):
    """Return Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def auth_context(client, session, test_master_data):
    """Register a master and return a direct JWT token and master ID."""
    from sqlalchemy import select
    from app.models.user import User

    reg_resp = await client.post("/api/v1/auth/register", json=test_master_data)
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.text}"
    master_id = reg_resp.json()["id"]
    user = (await session.execute(
        select(User).where(User.email == test_master_data["email"])
    )).scalar_one()
    token = master_access_token(user)

    return {"token": token, "master_id": master_id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
async def created_master_id(session, test_master_data):
    """Create a master directly in DB and return their master_profile ID."""
    from app.models.user import User, UserRole
    from app.models.master_profile import MasterProfile
    from app.utils.security import hash_password

    user = User(
        name=test_master_data["name"],
        email=test_master_data["email"],
        hashed_password=hash_password(test_master_data["password"]),
        phone=test_master_data["phone"],
        role=UserRole.MASTER,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    mp = MasterProfile(user_id=user.id)
    session.add(mp)
    await session.flush()
    await session.refresh(mp)

    await session.commit()  # Make visible to HTTP client sessions
    return mp.id  # API expects master_profile.id, not user.id


@pytest.fixture
def test_service_data():
    """Valid service creation data."""
    return {
        "name": "Шугаринг ног полностью",
        "description": "Удаление волос на ногах",
        "duration_minutes": 60,
        "price": 2500
    }


@pytest.fixture
def test_client_data():
    """Valid client creation data."""
    return {
        "name": "Анна Иванова",
        "phone": "+79991112233",
        "email": "anna@example.com"
    }


@pytest.fixture
def test_appointment_data():
    """Valid appointment creation data."""
    from datetime import datetime, timedelta
    future_date = datetime.now() + timedelta(days=7)
    return {
        "master_id": 1,
        "service_id": 1,
        "client_name": "Тест Клиент",
        "client_phone": "+79995556677",
        "appointment_date": future_date.isoformat()
    }


# ─── Super Admin Fixtures ────────────────────────────────────────────

@pytest.fixture
async def super_admin_user(session):
    """Create a super admin user directly in the database."""
    from app.models.user import User, UserRole
    from app.utils.security import hash_password

    user = User(
        name="Super Admin",
        email="superadmin@example.com",
        hashed_password=hash_password("SecurePass123!"),
        phone="+79990000000",
        role=UserRole.ADMIN,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


@pytest.fixture
async def super_admin_user_with_profile(session):
    """Create a super admin user with a MasterProfile for self-blocking tests."""
    from app.models.user import User, UserRole
    from app.models.master_profile import MasterProfile
    from app.utils.security import hash_password

    user = User(
        name="Super Admin 2",
        email="superadmin2@example.com",
        hashed_password=hash_password("SecurePass123!"),
        phone="+79990000001",
        role=UserRole.ADMIN,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)

    mp = MasterProfile(user_id=user.id)
    session.add(mp)
    await session.flush()
    await session.refresh(mp)

    return {"user": user, "master_profile": mp}


@pytest.fixture
async def super_admin_headers(session, super_admin_user):
    """Return Authorization headers for super admin requests."""
    from app.modules.auth.token import create_access_token

    token = create_access_token({
        "sub": str(super_admin_user.id),
        "role": super_admin_user.role.value,
        "name": super_admin_user.name,
        "is_admin": True,
    })
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def super_admin_headers_2(session, super_admin_user_with_profile):
    """Return Authorization headers for super admin requests (with profile)."""
    from app.modules.auth.token import create_access_token

    token = create_access_token({
        "sub": str(super_admin_user_with_profile["user"].id),
        "role": super_admin_user_with_profile["user"].role.value,
        "name": super_admin_user_with_profile["user"].name,
        "is_admin": True,
    })
    return {"Authorization": f"Bearer {token}"}

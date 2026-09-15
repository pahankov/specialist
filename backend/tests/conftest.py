"""
Pytest configuration for Sugar Booking backend tests.
"""
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db

# Test database URL (in-memory SQLite)
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


# ─── Database Fixtures ───────────────────────────────────────────────

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="function")
async def engine():
    """Create test database engine for each test function."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def session(engine) -> AsyncSession:
    """Create a new session with rollback (transaction isolation)."""
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as s:
        yield s
        await s.rollback()


# ─── HTTP Client Fixture ─────────────────────────────────────────────

@pytest.fixture(scope="function")
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
        "telegram_username": "test_master"
    }


@pytest.fixture
async def auth_token(client, test_master_data):
    """Register a master and return JWT token."""
    # Register
    resp = await client.post("/api/v1/auth/register", json=test_master_data)
    assert resp.status_code == 201, f"Register failed: {resp.text}"

    # Login
    login_data = {
        "email": test_master_data["email"],
        "password": test_master_data["password"]
    }
    resp = await client.post("/api/v1/auth/login", params=login_data)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]

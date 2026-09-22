"""
Pytest configuration for Online Booking backend tests.
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
    resp = await client.post("/api/v1/auth/register", json=test_master_data)
    assert resp.status_code == 201, f"Register failed: {resp.text}"

    login_data = {
        "email": test_master_data["email"],
        "password": test_master_data["password"]
    }
    resp = await client.post("/api/v1/auth/login", json=login_data)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Return Authorization headers for authenticated requests."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def auth_context(client, test_master_data):
    """Register a master and return both JWT token and master ID."""
    reg_resp = await client.post("/api/v1/auth/register", json=test_master_data)
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.text}"
    master_id = reg_resp.json()["id"]

    login_data = {
        "email": test_master_data["email"],
        "password": test_master_data["password"]
    }
    login_resp = await client.post("/api/v1/auth/login", json=login_data)
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["access_token"]

    return {"token": token, "master_id": master_id, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture
async def created_master_id(client, test_master_data):
    """Register a master and return their ID."""
    resp = await client.post("/api/v1/auth/register", json=test_master_data)
    assert resp.status_code == 201
    return resp.json()["id"]


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

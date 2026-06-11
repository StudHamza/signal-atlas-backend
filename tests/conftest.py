"""
Shared pytest fixtures.

Uses an in-memory SQLite database so tests never need a real Postgres instance.
The API key is fixed to "test-key" via environment variable.
"""
import os
import pytest

os.environ["API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from main import app

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Patch Geography column type for SQLite compatibility.
# geoalchemy2.Geography is PostGIS-only; SQLite can't create geography columns.
# Import is wrapped so conftest loads even when geoalchemy2 is not yet installed.
try:
    from app.models import CoverageRequest
except ImportError:
    CoverageRequest = None

if CoverageRequest is not None:
    @sa.event.listens_for(CoverageRequest.__table__, 'before_create')
    def _replace_geography_with_string(target, connection, **kw):
        target.c.area.type = sa.String()

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    """Set up the database structure once for the entire test session."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("test.db"):
        os.remove("test.db")

@pytest.fixture(scope="function")
def db_session():
    """
    Creates a fresh database session for each test, wrapped in a transaction.
    Rolls back any changes after the test completes to prevent state bleed.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    # Teardown: roll back the transaction and close connections
    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope="function")
def client(db_session):
    """
    Test client that overrides the FastAPI get_db dependency 
    to use our isolated, transactional db_session.
    """
    def override_get_db_for_test():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db_for_test
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture()
def auth_headers():
    return {"X-API-Key": "test-key"}

@pytest.fixture()
def jwt_headers(test_user):
    _, headers = test_user
    return headers

@pytest.fixture()
def sample_coverage_request():
    return {
        "title": "Downtown London Coverage",
        "description": "Need better coverage in central London",
        "country": "GB",
        "city": "London",
        "reward_amount": 100.00,
        "target_density_score": 50.0,
        "area": {
            "type": "Polygon",
            "coordinates": [[
                [-0.13, 51.50],
                [-0.12, 51.50],
                [-0.12, 51.51],
                [-0.13, 51.51],
                [-0.13, 51.50]
            ]]
        },
        "created_by": "user-123",
    }

@pytest.fixture()
def sample_reading():
    return {
        "source": "device-001",
        "timestamp": "2024-06-01T12:00:00Z",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "altitude": 20.0,
        "rsrp": -85,
        "rsrq": -10,
        "rssi": -70,
        "networkType": "LTE",
        "operator": "TestNet",
        "country": "GB",
        "city": "London",
    }

@pytest.fixture
def sample_device_id():
    return "abc123"


@pytest.fixture
def sample_profile():
    return {"username": "testuser"}


from uuid import uuid4
from decimal import Decimal
from app.models import Profile, UserDevice
from app.auth import UserInfo, get_current_user, require_user

@pytest.fixture
def test_user(db_session):
    """Create a test user directly in DB and return (user_id, auth_headers).
    Overrides require_user dependency to bypass JWT validation for tests.
    """
    uid = uuid4()
    profile = Profile(id=uid, username="testuser", credits=Decimal("10000"))
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)

    def _override():
        return UserInfo(id=uid, email="test@example.com")
    app.dependency_overrides[require_user] = _override
    app.dependency_overrides[get_current_user] = _override

    yield str(uid), {"X-API-Key": "test-key", "Authorization": "Bearer test-token"}

    app.dependency_overrides.pop(require_user, None)
    app.dependency_overrides.pop(get_current_user, None)
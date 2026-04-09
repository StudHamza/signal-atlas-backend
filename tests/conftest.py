"""
Shared pytest fixtures.

Uses an in-memory SQLite database so tests never need a real Postgres instance.
The API key is fixed to "test-key" via environment variable.
"""
import os
import pytest

os.environ["API_KEYS"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from main import app

TEST_DB_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

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
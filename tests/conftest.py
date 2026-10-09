import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from backend.app.core.database import Base, setup_database_triggers
from backend.app.api.deps import get_db
from backend.app.main import app
from backend.app.core.security import get_password_hash, create_access_token
from backend.app.models.user import User

# In-memory shared SQLite database for isolated test execution
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(autouse=True)
def setup_test_tables():
    Base.metadata.create_all(bind=test_engine)
    setup_database_triggers(test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_users(db):
    user1 = User(
        email="citizen1@example.com",
        name="Citizen One",
        hashed_password=get_password_hash("Secret123!"),
        role="CITIZEN",
    )
    user2 = User(
        email="citizen2@example.com",
        name="Citizen Two",
        hashed_password=get_password_hash("Secret123!"),
        role="CITIZEN",
    )
    officer = User(
        email="officer1@bbmp.gov.in",
        name="Officer Venkat",
        hashed_password=get_password_hash("Secret123!"),
        role="OFFICER",
    )
    db.add_all([user1, user2, officer])
    db.commit()
    db.refresh(user1)
    db.refresh(user2)
    db.refresh(officer)
    return {"user1": user1, "user2": user2, "officer": officer}


@pytest.fixture
def user1_token(test_users):
    return create_access_token(subject=test_users["user1"].id)


@pytest.fixture
def user2_token(test_users):
    return create_access_token(subject=test_users["user2"].id)


@pytest.fixture
def officer_token(test_users):
    return create_access_token(subject=test_users["officer"].id)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401 - registers all tables with Base
from app.api.chat import ChatPipeline, get_pipeline
from app.api.legal import get_legal_index
from app.api.reminders import get_email, get_telegram
from app.api.rsge import get_rs_client
from app.chat.extractor import KeywordExtractor
from app.chat.responder import TemplateResponder
from app.database import Base, get_db
from app.main import app

PASSWORD = "correct horse battery"


@pytest.fixture
def make_client():
    """Factory for TestClients sharing one in-memory DB; each has its own cookie jar (i.e. its own login)."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_conn, _):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine, autoflush=False)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    # Never call the real API or read a real legal index from tests, whatever the environment says.
    app.dependency_overrides[get_pipeline] = lambda: ChatPipeline(KeywordExtractor(), TemplateResponder(), "keyword", "template")
    app.dependency_overrides[get_legal_index] = lambda: None
    app.dependency_overrides[get_rs_client] = lambda: None
    app.dependency_overrides[get_email] = lambda: None
    app.dependency_overrides[get_telegram] = lambda: None

    def make(email: str | None = None) -> TestClient:
        client = TestClient(app)
        if email:
            response = client.post("/auth/register", json={"email": email, "password": PASSWORD, "full_name": "Test"})
            assert response.status_code == 201, response.text
        return client

    yield make
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def client(make_client):
    """Signed in as a fresh user."""
    return make_client("owner@example.com")

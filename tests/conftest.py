import pytest
from fastapi.testclient import TestClient

from app.core.database import Base, get_engine
from app.main import app
from app.repositories import models  # noqa: F401


@pytest.fixture(autouse=True)
def reset_database() -> None:
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DB_PATH = Path(".pytest_cache/test_workflow_assistant.db").resolve()
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
os.environ["AWA_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH.as_posix()}"
os.environ.setdefault("AWA_DEBUG", "false")

from app.core.database import Base, get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.repositories import models  # noqa: E402,F401


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

from collections.abc import Generator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for ORM models."""


def _sqlite_connect_args(database_url: str) -> dict[str, bool]:
    return {"check_same_thread": False} if database_url.startswith("sqlite") else {}


def _prepare_sqlite_path(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return

    sqlite_path = database_url.removeprefix("sqlite:///")
    if not sqlite_path or sqlite_path == ":memory:":
        return

    path = Path(sqlite_path)
    if path.parent != Path("."):
        path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_engine():
    settings = get_settings()
    _prepare_sqlite_path(settings.database_url)
    return create_engine(
        settings.database_url,
        future=True,
        echo=settings.debug,
        connect_args=_sqlite_connect_args(settings.database_url),
    )


SessionLocal = sessionmaker(
    bind=get_engine(),
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.repositories import models  # noqa: F401

    Base.metadata.create_all(bind=get_engine())

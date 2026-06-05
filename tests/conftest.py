"""Shared pytest fixtures.

Strategy: each test session gets ONE in-memory SQLite engine, and each test
function gets a fresh transactional session that rolls back at teardown. The
FastAPI app's `get_session` dependency is overridden to hand out the same
engine so TestClient + the unit-test sessions agree on the schema.

We DON'T run alembic for unit tests — schema goes up via `Base.metadata`.
A dedicated test in `test_migration.py` exercises the alembic path itself.
"""
from __future__ import annotations

import os

# Pin the DB URL BEFORE any app module imports — `app.config` resolves env at
# import time, then `app.db` builds its engine from `settings.db.url`. We point
# everything at a per-session tmp file. We ALWAYS override whatever the shell /
# .env had, so a stray `HPERSIST_DB__URL` pointing at the user's dev DB doesn't
# get wiped by the tests' schema reset.
import tempfile
from collections.abc import Iterator
from pathlib import Path

_TMP_DB = Path(tempfile.mkdtemp(prefix="hpersist-test-")) / "test.db"
os.environ["HPERSIST_DB__URL"] = f"sqlite:///{_TMP_DB}"

# ruff: noqa: E402 — imports below are deliberately deferred so the env var above
# takes effect before pydantic-settings reads it.
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401 — register models on Base
from app.db import Base
from app.db import engine as _engine

REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    """Create all tables once per session against the test engine."""
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture
def db_session() -> Iterator[Session]:
    """Per-test session — caller must commit explicitly; rollback at teardown."""
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)
    s = SessionLocal()
    try:
        yield s
    finally:
        s.rollback()
        # Wipe data between tests so they stay independent. Schema stays put.
        for table in reversed(Base.metadata.sorted_tables):
            s.execute(table.delete())
        s.commit()
        s.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    """FastAPI TestClient against the session engine."""
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return REPO_ROOT / "tests" / "fixtures"

"""Pytest configuration and shared fixtures.

Supports two modes:

LOCAL (no DATABASE_URL set, or DATABASE_URL=sqlite://...):
  Uses an on-disk SQLite file so developers can run `pytest` without a
  live Postgres instance.

CI (DATABASE_URL=postgresql://...):
  Uses the Postgres service container provided by GitHub Actions.
  This mode is activated when DATABASE_URL is already set to a
  postgresql:// URL *before* pytest starts — the CI workflow sets it
  as an environment variable.  In this mode, Alembic migrations are
  expected to have already run (the CI workflow does `alembic upgrade head`
  as a dedicated step before running pytest).

The DATABASE_URL check happens before any app modules are imported so
SQLAlchemy picks up the correct engine on first import.
"""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# ── Determine database URL ──────────────────────────────────────────────────
_existing_url = os.environ.get("DATABASE_URL", "")

if _existing_url.startswith("postgresql"):
    # CI mode — use the real Postgres service container.
    # DATABASE_URL is already exported by the workflow; don't touch it.
    TEST_DATABASE_URL = _existing_url
    _connect_args: dict = {}
    _ci_mode = True
else:
    # Local mode — fall back to SQLite so no Postgres is needed.
    TEST_DATABASE_URL = "sqlite:///./test.db"
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    _connect_args = {"check_same_thread": False}
    _ci_mode = False

os.environ.setdefault("APP_BASE_URL", "http://testserver")

# Import app modules AFTER setting DATABASE_URL
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

engine = create_engine(TEST_DATABASE_URL, connect_args=_connect_args)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function", autouse=True)
def setup_db():
    """Create tables before each test; truncate (Postgres) or drop (SQLite) after.

    In CI mode (Postgres): Alembic has already created the schema. We just
    truncate rows between tests for isolation without re-running migrations.

    In local mode (SQLite): Create and drop tables for full isolation.
    """
    if _ci_mode:
        # Tables already exist from `alembic upgrade head` in the CI step.
        # Truncate all data between tests for isolation.
        yield
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE links RESTART IDENTITY CASCADE"))
    else:
        Base.metadata.create_all(bind=engine)
        yield
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client():
    """Return a TestClient with the DB dependency overridden to use the test engine."""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()

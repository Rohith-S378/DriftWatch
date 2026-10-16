"""
Pytest configuration and shared fixtures for DriftWatch tests.

All tests use an isolated in-memory SQLite database so they never touch
production data and require no external services.
"""
import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.pool import StaticPool

# Force SQLite for the test session BEFORE importing app modules.
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app.db.database import Base  # noqa: E402
from app.models import models  # noqa: E402  (ensure models are imported)


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    SessionLocal = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    async with SessionLocal() as session:
        yield session


@pytest.fixture
def client(session):
    """FastAPI TestClient wired to the test session."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import get_db

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
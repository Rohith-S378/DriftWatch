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
# Pre-auth tests create legacy fixtures without user_id; allow global reads in test suite
os.environ["ALLOW_LEGACY_GLOBAL_READS"] = "true"

from app.db.database import Base  # noqa: E402
from app.models import models  # noqa: E402  (ensure models are imported)
from app.auth import require_user  # noqa: E402


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
    """FastAPI TestClient wired to the test session.

    Business routes now require authentication (require_user). Tests that
    exercise those routes get a deterministic test user injected via a
    dependency override, so the pre-auth test suite keeps working without
    each test needing to log in. Auth-specific routes (register/login/me/
    status/logout) are NOT overridden — they use the real get_current_user,
    so test_auth.py's 401/cookie assertions still hold.

    The override is cookie-aware: when a request carries a real session
    cookie it delegates to the genuine session validation, so auth tests
    that manipulate cookies still observe real session semantics. Only
    anonymous requests (no cookie) fall back to the test user.
    """
    import uuid as _uuid
    from datetime import datetime, timezone
    from fastapi import Depends, Request
    from fastapi.testclient import TestClient
    from app.main import app
    from app.db.database import get_db
    from app.models.auth import User
    from app.auth import require_user, get_session_token
    from app.csrf import require_csrf

    async def _override_get_db():
        yield session

    async def _real_get_current_user(request, db):
        """Re-implementation of app.auth.get_current_user using the test session."""
        from sqlalchemy import select
        from app.models.auth import Session as S, User as U
        from app.auth import _get_session_from_cookie
        token = get_session_token(request)
        if not token:
            return None
        sess = await _get_session_from_cookie(token, db)
        if not sess:
            return None
        res = await db.execute(select(U).where(U.id == sess.user_id))
        return res.scalar_one_or_none()

    async def _override_require_user(request: Request, db: AsyncSession = Depends(get_db)):
        """Cookie-aware stand-in for app.auth.require_user.

        Business routes depend on require_user (which depends on
        get_current_user). We override require_user directly so the auth
        routes — which depend on get_current_user — keep their real
        behaviour. When a real session cookie is present we validate it the
        normal way; anonymous requests get the deterministic test user.
        """
        token = get_session_token(request)
        if token:
            user = await _real_get_current_user(request, db)
            if user is not None:
                return user
        user = User(
            id=_uuid.UUID("00000000-0000-4000-8000-000000000001"),
            email="test@example.com",
            password_hash="",
            display_name="Test User",
            is_active=True,
            is_verified=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        return user

    def _override_csrf(request: Request):
        """Test override: skip CSRF validation for pre-auth tests.

        Real CSRF behaviour is exercised by tests/test_csrf.py, which does
        not use this override. The override exists so the existing pre-auth
        test suite (which posts to state-changing routes without a CSRF
        token) keeps working after CSRF enforcement was added.
        """
        return ""

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[require_user] = _override_require_user
    app.dependency_overrides[require_csrf] = _override_csrf
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
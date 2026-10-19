"""Tests for DriftWatch authentication and session handling.

These tests exercise the real FastAPI middleware, password hashing, and the
server-side session/authorization logic against an isolated in-memory
SQLite database (see conftest.py). No live external services are required.

Covered scenarios:
- Registration (success, duplicate, invalid input)
- Login (success, invalid credentials, generic error)
- Session establishment (HttpOnly cookie, CSRF cookie)
- /auth/me for authenticated and anonymous callers
- Logout revokes the session
- Unauthenticated protected request is rejected (401)
- Cross-user session isolation: a token from user A does not authenticate
  as user B
- Expired sessions are rejected
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.auth import User, Session


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────

def _register(client, email="alice@example.com", password="correct-horse-1", name="Alice"):
    return client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "display_name": name},
    )


def _login(client, email="alice@example.com", password="correct-horse-1"):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


# ────────────────────────────────────────────────────────────────────────────
# Registration
# ────────────────────────────────────────────────────────────────────────────

def test_register_success(client):
    res = _register(client)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "registered"
    assert body["user"]["email"] == "alice@example.com"
    # A session cookie must be set
    assert "dw_session" in res.cookies
    # A CSRF token must be returned for the client to send on state-changing requests
    assert "csrf_token" in body


def test_register_duplicate_email(client):
    first = _register(client, email="dup@example.com")
    assert first.status_code == 200
    second = _register(client, email="DUP@example.com")  # case-insensitive dup
    assert second.status_code == 400


def test_register_invalid_email(client):
    res = client.post("/api/auth/register", json={"email": "not-an-email", "password": "correct-horse-1"})
    assert res.status_code == 400


def test_register_short_password(client):
    res = client.post("/api/auth/register", json={"email": "short@example.com", "password": "abc"})
    assert res.status_code == 400
    assert "8 characters" in res.json()["detail"]


def test_register_does_not_leak_password_hash(client):
    res = _register(client)
    assert res.status_code == 200
    # The response must not contain any hash or password field
    text = res.text
    assert "password_hash" not in text
    assert "correct-horse-1" not in text


# ────────────────────────────────────────────────────────────────────────────
# Login
# ────────────────────────────────────────────────────────────────────────────

def test_login_success(client):
    _register(client)
    res = _login(client)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "logged_in"
    assert "dw_session" in res.cookies


def test_login_invalid_password(client):
    _register(client, password="correct-horse-1")
    res = _login(client, password="wrong-password-9")
    assert res.status_code == 401
    # Generic error must not reveal which part failed
    assert res.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_same_error(client):
    res = _login(client, email="ghost@example.com")
    assert res.status_code == 401
    assert res.json()["detail"] == "Invalid email or password"


# ────────────────────────────────────────────────────────────────────────────
# /auth/me + session
# ────────────────────────────────────────────────────────────────────────────

def test_me_requires_auth(client):
    res = client.get("/api/auth/me")
    assert res.status_code == 401


def test_me_returns_current_user(client):
    _register(client, email="bob@example.com", name="Bob")
    res = client.get("/api/auth/me")
    assert res.status_code == 200, res.text
    assert res.json()["email"] == "bob@example.com"
    assert res.json()["display_name"] == "Bob"


def test_auth_status_unauthenticated(client):
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json()["authenticated"] is False


def test_auth_status_authenticated(client):
    _register(client)
    res = client.get("/api/auth/status")
    assert res.status_code == 200
    assert res.json()["authenticated"] is True
    assert res.json()["user"]["email"] == "alice@example.com"


def test_logout_revokes_session(client):
    _register(client)
    # Confirm we're authenticated first
    assert client.get("/api/auth/me").status_code == 200
    res = client.post("/api/auth/logout")
    assert res.status_code == 200
    # After logout, the session should no longer be valid
    assert client.get("/api/auth/me").status_code == 401


# ────────────────────────────────────────────────────────────────────────────
# Cross-user isolation & expired sessions
# ────────────────────────────────────────────────────────────────────────────

def test_cross_user_session_isolation(client):
    # Register two users in the same TestClient (shared cookie jar).
    _register(client, email="alice@example.com", name="Alice")
    token_a = client.cookies.get("dw_session")
    assert token_a

    # Re-register as Bob, which replaces the cookie in the shared jar
    _register(client, email="bob@example.com", name="Bob")
    token_b = client.cookies.get("dw_session")
    assert token_b and token_a != token_b

    # Explicitly present Alice's token: she must be authenticated as Alice,
    # NOT as Bob, and must not see Bob's identity.
    client.cookies.set("dw_session", token_a)
    me = client.get("/api/auth/me").json()
    assert me["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_expired_session_rejected(client, session):
    """A session whose expires_at is in the past must be rejected (401).

    The conftest `session` fixture is the *same* in-memory engine the TestClient
    is wired to via the `get_db` override, so we can reach the exact session row
    the register call wrote and age it in place.
    """
    from sqlalchemy import select as _sel
    from app.models.auth import Session as S

    _register(client)
    token = client.cookies.get("dw_session")

    res = await session.execute(_sel(S).where(S.session_token == token))
    sess = res.scalar_one_or_none()
    assert sess is not None
    # SQLite stores naive datetimes; write a naive expiry in the past.
    sess.expires_at = datetime.utcnow() - timedelta(hours=1)
    await session.commit()

    resp = client.get("/api/auth/me")
    assert resp.status_code == 401

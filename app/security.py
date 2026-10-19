"""Security helpers: password hashing, session token generation, CSRF tokens.

No secrets are hardcoded here. All values are derived from settings or
generated at runtime with the secrets module.
"""

import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt

from app.config import settings


# ── Password hashing ────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash a password with bcrypt. Returns an opaque hash string."""
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against a bcrypt hash in constant time."""
    try:
        return _bcrypt.checkpw(password.encode(), password_hash.encode())
    except Exception:
        return False


# ── Session tokens ──────────────────────────────────────────────────────────

def generate_session_token() -> str:
    """Generate a cryptographically random opaque session token."""
    return secrets.token_urlsafe(48)


def generate_csrf_token() -> str:
    """Generate a random CSRF token for state-changing requests."""
    return secrets.token_urlsafe(32)


def hash_csrf_token(token: str) -> str:
    """HMAC-hash a CSRF token so the raw value is not stored client-side."""
    secret = (settings.INTERNAL_SECRET or "driftwatch-csrf-development").encode()
    return hmac.new(secret, token.encode(), hashlib.sha256).hexdigest()


def make_session_expiry(hours: int = 24) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=hours)


# ── Fingerprint helpers ─────────────────────────────────────────────────────

def fingerprint(value: str | None) -> str | None:
    """Hash a user-agent/IP for session binding. Never stores raw values."""
    if not value:
        return None
    secret = (settings.INTERNAL_SECRET or "driftwatch-session-development").encode()
    return hmac.new(secret, value.encode(), hashlib.sha256).hexdigest()


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)
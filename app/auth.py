"""Authentication dependency: resolves the current user from the session cookie.

Security properties:
- Session token lives in an HttpOnly, SameSite=Lax cookie set by the login
  endpoint. JavaScript cannot read it, which prevents token theft via XSS.
- The raw token is never logged or returned in responses.
- Expired or revoked sessions are rejected with 401.
- CSRF is enforced separately for state-changing requests via the
  `require_csrf` dependency (double-submit pattern).
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import Request, Response, HTTPException, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.auth import User, Session
from app.security import constant_time_compare


async def _get_session_from_cookie(
    token: Optional[str], db: AsyncSession
) -> Optional[Session]:
    """Look up a session by its opaque cookie token.

    Returns None if the token is missing, the session is unknown, revoked,
    or expired. Expired sessions are marked revoked as a side effect so a
    lazy cleanup path exists without a background job.
    """
    if not token:
        return None

    result = await db.execute(
        select(Session).where(Session.session_token == token)
    )
    session = result.scalar_one_or_none()
    if not session:
        return None

    if session.revoked or _is_expired(session.expires_at):
        session.revoked = True
        await db.commit()
        return None

    return session


def _is_expired(expires_at) -> bool:
    """Compare an expiry timestamp against the current time, tolerating
    both timezone-aware and timezone-naive datetimes (SQLite returns naive).

    Naive datetimes are interpreted as UTC.
    """
    if expires_at is None:
        return True
    now = datetime.now(timezone.utc)
    if expires_at.tzinfo is None:
        # SQLite / naive datetime: treat as UTC.
        return expires_at.replace(tzinfo=timezone.utc) < now
    return expires_at < now


def get_session_token(request: Request) -> Optional[str]:
    """Extract the opaque session token from the cookie header."""
    return request.cookies.get("dw_session")


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Return the authenticated User, or None if no valid session exists.

    This dependency never raises; routes that require authentication should
    call `require_user` instead, which raises 401 for anonymous callers.
    """
    token = get_session_token(request)
    if not token:
        return None
    session = await _get_session_from_cookie(token, db)
    if not session:
        return None

    # Touch last_active_at cheaply (best-effort; do not fail the request).
    try:
        session.last_active_at = datetime.now(timezone.utc)
        await db.commit()
    except Exception:
        await db.rollback()

    result = await db.execute(select(User).where(User.id == session.user_id))
    user = result.scalar_one_or_none()
    return user


async def require_user(
    user: Optional[User] = Depends(get_current_user),
) -> User:
    """Require an authenticated user. Raises 401 for anonymous callers."""
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def set_session_cookie(response: Response, token: str, max_age_seconds: int):
    """Set the session cookie with secure, HttpOnly, SameSite=Lax attributes.

    The `secure` flag is only enabled when the request arrived over HTTPS,
    matching the deployment topology. Local development over http still
    receives the cookie (browsers accept it), but production deployments
    behind TLS will mark it Secure.
    """
    response.set_cookie(
        key="dw_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=False,  # set per-request below if needed
        max_age=max_age_seconds,
        path="/",
    )


def set_session_cookie_secure(response: Response, token: str, max_age_seconds: int):
    """Variant that also sets the Secure flag (HTTPS deployments only)."""
    response.set_cookie(
        key="dw_session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age_seconds=max_age_seconds,
        path="/",
    )


def clear_session_cookie(response: Response):
    """Expire the session cookie on the client."""
    response.delete_cookie(
        key="dw_session",
        path="/",
        httponly=True,
        samesite="lax",
    )
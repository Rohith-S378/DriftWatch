"""CSRF protection via double-submit cookie pattern.

State-changing requests (POST/PUT/PATCH/DELETE) must include an
`X-CSRF-Token` header whose value matches the `dw_csrf` cookie set at
login time. The raw token is never stored server-side; only an HMAC hash
is persisted, so a database leak does not expose usable CSRF tokens.

This is deliberately simple and framework-agnostic: no per-form tokens,
no synchronizer token pattern complexity. It is sufficient for a
same-origin SPA where the cookie is SameSite=Lax.
"""

import hashlib
import hmac
from typing import Optional

from fastapi import Request, HTTPException

from app.security import hash_csrf_token


CSRF_COOKIE_NAME = "dw_csrf"
CSRF_HEADER_NAME = "x-csrf-token"


def get_csrf_cookie(request: Request) -> Optional[str]:
    return request.cookies.get(CSRF_COOKIE_NAME)


def get_csrf_header(request: Request) -> Optional[str]:
    return request.headers.get(CSRF_HEADER_NAME)


def issue_csrf_token() -> str:
    """Generate a fresh random CSRF token (caller stores hash server-side)."""
    import secrets
    return secrets.token_urlsafe(32)


def verify_csrf(request: Request, stored_hash: Optional[str]) -> bool:
    """Compare the submitted header token against the stored hash."""
    cookie = get_csrf_cookie(request)
    header = get_csrf_header(request)
    if not cookie or not header or not stored_hash:
        return False
    # Constant-time compare of the submitted token's hash with the stored hash.
    submitted_hash = hash_csrf_token(header)
    return hmac.compare_digest(submitted_hash, stored_hash)


def require_csrf(request: Request) -> str:
    """Dependency: ensure the request carries a valid CSRF token.

    Returns the submitted raw token (for use in issuing a fresh pair on
    login). Raises 403 on mismatch.
    """
    cookie = get_csrf_cookie(request)
    header = get_csrf_header(request)
    if not cookie or not header:
        raise HTTPException(
            status_code=403,
            detail="Missing CSRF token",
        )
    if not hmac.compare_digest(cookie, header):
        raise HTTPException(
            status_code=403,
            detail="CSRF token mismatch",
        )
    return header
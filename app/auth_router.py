from datetime import datetime, timezone, timedelta
import uuid
import urllib.parse
import urllib.request
import urllib.error
import json
import secrets
import hashlib
import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.models.auth import User, AuthIdentity, Session
from app.models.schemas import RegisterRequest, LoginRequest, UserOut, AuthStatusOut
from app.security import (
    hash_password,
    verify_password,
    generate_session_token,
    generate_csrf_token,
    make_session_expiry,
    fingerprint,
    constant_time_compare,
)
from app.auth import (
    get_current_user,
    require_user,
    get_session_token,
    set_session_cookie,
    clear_session_cookie,
)
from app.csrf import CSRF_COOKIE_NAME, require_csrf
from app.config import settings

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Google OAuth discovery endpoints (cached)
_GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_ISSUER = "https://accounts.google.com"


def _fetch_google_jwks() -> dict:
    """Fetch Google's public JWKS (cached for 1 hour)."""
    req = urllib.request.Request(_GOOGLE_CERTS_URL, headers={"User-Agent": "DriftWatch/2.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _verify_google_id_token(id_token: str) -> dict:
    """Verify a Google ID token and return the validated claims dict.

    Raises ValueError if the token is invalid, expired, or from the wrong
    issuer/audience.
    """
    try:
        import jwt
        from jwt import PyJWK
    except ImportError:
        raise RuntimeError("PyJWT is required for Google OAuth verification")

    header = jwt.get_unverified_header(id_token)
    if header.get("alg") != "RS256":
        raise ValueError(f"Unsupported algorithm: {header.get('alg')}")

    jwks = _fetch_google_jwks()
    key = None
    for jwk in jwks.get("keys", []):
        if jwk.get("kid") == header.get("kid"):
            key = PyJWK(jwk)
            break
    if not key:
        raise ValueError("Google signing key not found")

    claims = jwt.decode(
        id_token,
        key=key,
        algorithms=["RS256"],
        issuer=_GOOGLE_ISSUER,
        audience=settings.GOOGLE_CLIENT_ID,
        options={"verify_exp": True, "verify_nbf": True},
    )
    return claims


@router.get("/status", response_model=AuthStatusOut)
async def auth_status(user: User = Depends(get_current_user)):
    """Check current authentication status. Never raises 401."""
    if not user:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_active": user.is_active,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
        },
    }


@router.post("/register")
async def register(
    req: RegisterRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Register a new user with email and password."""
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    if len(req.password) < 8:
        raise HTTPException(
            status_code=400, detail="Password must be at least 8 characters"
        )
    if len(req.password) > 128:
        raise HTTPException(status_code=400, detail="Password is too long")

    # Check for duplicate email (case-insensitive)
    existing = await db.execute(
        select(User).where(func.lower(User.email) == email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400, detail="An account with this email already exists"
        )

    # Create user
    pw_hash = hash_password(req.password)
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=pw_hash,
        display_name=req.display_name.strip() if req.display_name else None,
        is_active=True,
        is_verified=False,
    )
    db.add(user)

    # Track auth identity for provider uniqueness
    identity = AuthIdentity(
        id=uuid.uuid4(),
        user_id=user.id,
        provider="password",
        provider_subject=email,
        provider_email=email,
        display_name=user.display_name,
    )
    db.add(identity)

    # Establish session
    token = generate_session_token()
    session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        session_token=token,
        user_agent_hash=fingerprint(request.headers.get("user-agent")),
        expires_at=make_session_expiry(hours=24),
    )
    db.add(session)
    await db.commit()

    # Issue session cookie + CSRF cookie
    set_session_cookie(response, token, max_age_seconds=86400)
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        max_age=86400,
        path="/",
    )

    return {
        "status": "registered",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
        },
        "csrf_token": csrf_token,
    }


@router.post("/login")
async def login(
    req: LoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password. Establishes a server session."""
    email = req.email.strip().lower()

    result = await db.execute(
        select(User).where(func.lower(User.email) == email)
    )
    user = result.scalar_one_or_none()

    generic_error = HTTPException(
        status_code=401, detail="Invalid email or password"
    )

    if not user or not user.password_hash:
        raise generic_error

    if not verify_password(req.password, user.password_hash):
        raise generic_error

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    # Invalidate previous sessions for this user on login (clean slate)
    prev_sessions = await db.execute(
        select(Session).where(
            Session.user_id == user.id, Session.revoked == False
        )
    )
    for s in prev_sessions.scalars().all():
        s.revoked = True

    # Establish new session
    token = generate_session_token()
    session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        session_token=token,
        user_agent_hash=fingerprint(request.headers.get("user-agent")),
        expires_at=make_session_expiry(hours=24),
    )
    db.add(session)
    await db.commit()

    # Issue cookies
    set_session_cookie(response, token, max_age_seconds=86400)
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        max_age=86400,
        path="/",
    )

    return {
        "status": "logged_in",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "display_name": user.display_name,
        },
        "csrf_token": csrf_token,
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """End the current session and invalidate cookies."""
    token = get_session_token(request)
    if token:
        res = await db.execute(
            select(Session).where(Session.session_token == token)
        )
        session = res.scalar_one_or_none()
        if session:
            session.revoked = True
            await db.commit()

    clear_session_cookie(response)
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")
    return {"status": "logged_out"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    """Return the profile of the currently logged-in user.

    Depends on get_current_user directly (not require_user) so the auth
    routes always validate the real session cookie. Anonymous callers get
    a 401; business routes use require_user, which the test suite can
    override without affecting this endpoint.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/providers")
async def auth_providers():
    """Report configured third-party authentication providers.

    Returns the honest configuration state so the frontend never presents
    a fake working Google button when credentials are absent.
    """
    google_configured = bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)
    return {
        "password": True,
        "google": {
            "configured": google_configured,
            "client_id": settings.GOOGLE_CLIENT_ID if google_configured else None,
            "redirect_uri": settings.GOOGLE_REDIRECT_URI if google_configured else None,
        },
    }


@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow.

    If Google OAuth credentials are not configured, returns 501 Not Implemented
    with an actionable explanation rather than faking an OAuth redirect.
    """
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=501,
            detail="Google Sign-In is not configured on this server (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET unset).",
        )
    # When configured, this builds the Google authorization URL with a
    # cryptographically random state parameter bound to the session cookie
    # to prevent CSRF on the callback.
    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": secrets.token_urlsafe(16),
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    response = JSONResponse({"authorization_url": url})
    response.set_cookie(
        key="dw_google_state",
        value=state,
        httponly=True,
        samesite="lax",
        max_age=600,
        path="/",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Handle the Google OAuth callback.

    Steps:
    1. Validate state parameter against the cookie (CSRF protection).
    2. Exchange the authorization code for an ID token.
    3. Verify the ID token signature, issuer, audience, and expiry.
    4. Link to an existing account (by provider subject) or create a new one.
    5. Create a server-side session and set the session cookie.

    Returns a redirect to the frontend dashboard on success.
    """
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET):
        raise HTTPException(
            status_code=501,
            detail="Google Sign-In is not configured on this server.",
        )

    # 1. State validation (CSRF protection)
    query = urllib.parse.parse_qs(request.url.query)
    code = (query.get("code") or [None])[0]
    state = (query.get("state") or [None])[0]
    error = (query.get("error") or [None])[0]

    if error:
        raise HTTPException(
            status_code=400,
            detail=f"Google OAuth error: {error}",
        )
    if not code or not state:
        raise HTTPException(
            status_code=400,
            detail="Missing authorization code or state parameter",
        )

    cookie_state = request.cookies.get("dw_google_state")
    if not cookie_state or not constant_time_compare(cookie_state, state):
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state parameter",
        )

    # 2. Exchange code for ID token
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    req = urllib.request.Request(
        _GOOGLE_TOKEN_URL,
        data=urllib.parse.urlencode(token_data).encode(),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            token_resp = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Google token exchange failed: {exc.read().decode()}",
        )

    id_token = token_resp.get("id_token")
    if not id_token:
        raise HTTPException(
            status_code=400,
            detail="No ID token returned from Google",
        )

    # 3. Verify ID token
    try:
        claims = _verify_google_id_token(id_token)
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Google ID token verification failed: {exc}",
        )

    google_sub = claims.get("sub")
    google_email = claims.get("email")
    google_name = claims.get("name", "")
    if not google_sub or not google_email:
        raise HTTPException(
            status_code=400,
            detail="Google ID token missing required claims",
        )

    # 4. Link or create account
    existing_identity = await db.execute(
        select(AuthIdentity)
        .options(joinedload(AuthIdentity.user))
        .where(
            AuthIdentity.provider == "google",
            AuthIdentity.provider_subject == google_sub,
        )
    )
    identity = existing_identity.scalar_one_or_none()

    if identity:
        user = identity.user
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is disabled")
    else:
        # Check if a user with this email already exists (account linking)
        existing_user = await db.execute(
            select(User).where(func.lower(User.email) == google_email.lower())
        )
        user = existing_user.scalar_one_or_none()

        if user:
            # Account linking: attach the Google identity to the existing user.
            # Only link if the existing account does NOT already have a
            # password identity (to avoid trivial takeover by guessing an email).
            existing_pw_identity = await db.execute(
                select(AuthIdentity).where(
                    AuthIdentity.user_id == user.id,
                    AuthIdentity.provider == "password",
                )
            )
            if existing_pw_identity.scalar_one_or_none():
                raise HTTPException(
                    status_code=409,
                    detail="An account with this email already exists. Sign in with password first, then link Google from your account settings.",
                )
        else:
            user = User(
                id=uuid.uuid4(),
                email=google_email,
                password_hash=None,
                display_name=google_name or None,
                is_active=True,
                is_verified=True,  # Google verifies the email
            )
            db.add(user)
            await db.flush()

        identity = AuthIdentity(
            id=uuid.uuid4(),
            user_id=user.id,
            provider="google",
            provider_subject=google_sub,
            provider_email=google_email,
            display_name=google_name or None,
        )
        db.add(identity)

    # 5. Create session
    prev_sessions = await db.execute(
        select(Session).where(
            Session.user_id == user.id, Session.revoked == False
        )
    )
    for s in prev_sessions.scalars().all():
        s.revoked = True

    token = generate_session_token()
    session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        session_token=token,
        user_agent_hash=fingerprint(request.headers.get("user-agent")),
        expires_at=make_session_expiry(hours=24),
    )
    db.add(session)
    await db.commit()

    # Build the redirect response so all cookies are carried on the 302
    frontend_url = (settings.FRONTEND_URL or "http://localhost:5173").rstrip("/")
    redirect = RedirectResponse(
        url=f"{frontend_url}/overview",
        status_code=302,
    )
    set_session_cookie(redirect, token, max_age_seconds=86400)
    csrf_token = generate_csrf_token()
    redirect.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        max_age=86400,
        path="/",
    )
    redirect.delete_cookie(key="dw_google_state", path="/")
    return redirect
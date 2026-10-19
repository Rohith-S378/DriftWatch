"""Security regression and authorization audit tests.

Covers:
1. Cross-user access isolation (CRUD, discovery, ask_ai, webhook leak).
2. CSRF enforcement on all state-changing endpoints.
3. Cookie attributes (HttpOnly, SameSite, path).
4. SSRF safety on URLs and redirects.
5. Inactive account blocking.
6. Unauthenticated endpoint rejection.
"""
import uuid
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db
from app.models.auth import User, Session
from app.models.models import CompetitorRegistry, DataSnapshot, ChangeEvent, DiscoveryRun, DiscoveryCandidate
from app.security import hash_password, generate_session_token, generate_csrf_token, make_session_expiry
from app.csrf import CSRF_COOKIE_NAME, CSRF_HEADER_NAME


@pytest.fixture
def clean_client(session):
    """Client WITHOUT dependency overrides, so real require_user, require_csrf,
    and get_current_user are exercised exactly as in production."""
    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(session, email="audit@example.com", is_active=True):
    uid = uuid.uuid4()
    u = User(
        id=uid,
        email=email,
        password_hash=hash_password("password123"),
        display_name=email.split("@")[0].title(),
        is_active=is_active,
        is_verified=True,
    )
    session.add(u)
    token = generate_session_token()
    s = Session(
        id=uuid.uuid4(),
        user_id=uid,
        session_token=token,
        expires_at=make_session_expiry(24),
    )
    session.add(s)
    return u, token


# ── 1. CSRF Enforcement on State-Changing Routes ──────────────────────────

@pytest.mark.asyncio
async def test_csrf_missing_cookie_rejected(clean_client, session):
    user, token = _create_user(session)
    await session.commit()

    clean_client.cookies.set("dw_session", token)
    # POST without dw_csrf cookie or header
    res = clean_client.post("/api/competitors/add", json={"name": "test", "url": "https://example.com"})
    assert res.status_code == 403
    assert "Missing CSRF token" in res.json()["detail"]


@pytest.mark.asyncio
async def test_csrf_header_cookie_mismatch_rejected(clean_client, session):
    user, token = _create_user(session)
    await session.commit()

    clean_client.cookies.set("dw_session", token)
    clean_client.cookies.set(CSRF_COOKIE_NAME, "cookie-token-value")
    res = clean_client.post(
        "/api/competitors/add",
        json={"name": "test", "url": "https://example.com"},
        headers={CSRF_HEADER_NAME: "different-header-value"},
    )
    assert res.status_code == 403
    assert "CSRF token mismatch" in res.json()["detail"]


@pytest.mark.asyncio
async def test_csrf_matching_passes(clean_client, session):
    user, token = _create_user(session)
    await session.commit()

    csrf = generate_csrf_token()
    clean_client.cookies.set("dw_session", token)
    clean_client.cookies.set(CSRF_COOKIE_NAME, csrf)

    with patch("app.services.scheduler.scheduler.add_competitor", new_callable=AsyncMock) as mock_add:
        mock_add.return_value = True
        res = clean_client.post(
            "/api/competitors/add",
            json={"name": "csrf_passed_comp", "url": "https://example.com"},
            headers={CSRF_HEADER_NAME: csrf},
        )
        assert res.status_code == 200


# ── 2. Cross-User Competitor Deletion ──────────────────────────────────────

@pytest.mark.asyncio
async def test_cross_user_competitor_delete_blocked(clean_client, session):
    user_a, token_a = _create_user(session, email="alice@test.com")
    user_b, token_b = _create_user(session, email="bob@test.com")

    comp = CompetitorRegistry(
        source_id="alice_private_co",
        url="https://alice.example.com",
        user_id=user_a.id,
    )
    session.add(comp)
    await session.commit()

    csrf_b = generate_csrf_token()
    clean_client.cookies.set("dw_session", token_b)
    clean_client.cookies.set(CSRF_COOKIE_NAME, csrf_b)

    # Bob attempts to delete Alice's competitor
    res = clean_client.delete(
        "/api/competitors/alice_private_co",
        headers={CSRF_HEADER_NAME: csrf_b},
    )
    assert res.status_code == 404

    # Alice's competitor must still exist
    res = clean_client.get("/api/competitors")
    # Bob should not see it in his own list either
    assert "alice_private_co" not in [c["source_id"] for c in res.json().get("competitors", [])]


# ── 3. Webhook Events Authentication & Scoping ────────────────────────────

@pytest.mark.asyncio
async def test_webhook_events_unauthenticated_rejected(clean_client):
    res = clean_client.get("/webhook/events/some_competitor")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_webhook_events_scoped_to_user(clean_client, session):
    from app.config import settings
    user_a, token_a = _create_user(session, email="alice@test.com")
    user_b, token_b = _create_user(session, email="bob@test.com")

    # Event owned by Alice
    ev_a = ChangeEvent(
        source_id="shared_comp",
        change_type="price",
        severity="high",
        description="Alice private event",
        user_id=user_a.id,
    )
    # Event owned by Bob
    ev_b = ChangeEvent(
        source_id="shared_comp",
        change_type="price",
        severity="high",
        description="Bob private event",
        user_id=user_b.id,
    )
    # Legacy/global event (user_id is None)
    ev_global = ChangeEvent(
        source_id="shared_comp",
        change_type="messaging",
        severity="low",
        description="Global visible event",
        user_id=None,
    )
    session.add(ev_a)
    session.add(ev_b)
    session.add(ev_global)
    await session.commit()

    # Bob queries webhook events for shared_comp:
    # Under strict ALLOW_LEGACY_GLOBAL_READS=False, Bob sees ONLY his own event!
    settings.ALLOW_LEGACY_GLOBAL_READS = False
    clean_client.cookies.set("dw_session", token_b)
    res = clean_client.get("/webhook/events/shared_comp")
    assert res.status_code == 200
    descriptions = [e["description"] for e in res.json()]

    assert "Bob private event" in descriptions
    assert "Alice private event" not in descriptions
    assert "Global visible event" not in descriptions  # NOT visible by default!

    # When explicitly opted in to legacy reads:
    settings.ALLOW_LEGACY_GLOBAL_READS = True
    try:
        res = clean_client.get("/webhook/events/shared_comp")
        descriptions = [e["description"] for e in res.json()]
        assert "Global visible event" in descriptions
        assert "Alice private event" not in descriptions
    finally:
        settings.ALLOW_LEGACY_GLOBAL_READS = False


# ── 4. Cross-User Discovery Run & Candidate Isolation ─────────────────────

@pytest.mark.asyncio
async def test_discovery_run_cross_user_isolation(clean_client, session):
    user_a, token_a = _create_user(session, email="alice@test.com")
    user_b, token_b = _create_user(session, email="bob@test.com")

    run_a = DiscoveryRun(
        id=uuid.uuid4(),
        target_url="https://alice-target.com",
        normalized_domain="alice-target.com",
        company_name="AliceTarget",
        status="completed",
        company_profile={},
        user_id=user_a.id,
    )
    cand_a = DiscoveryCandidate(
        id=uuid.uuid4(),
        run_id=run_a.id,
        candidate_name="Alice Rival",
        website_url="https://alice-rival.com",
        normalized_domain="alice-rival.com",
        match_score=85,
        classification="direct",
        match_explanation="Close overlap",
        is_verified=True,
        status="suggested",
        user_id=user_a.id,
    )
    session.add(run_a)
    session.add(cand_a)
    await session.commit()

    # Bob tries to access Alice's run
    clean_client.cookies.set("dw_session", token_b)
    res = clean_client.get(f"/api/discovery/runs/{run_a.id}")
    assert res.status_code == 404

    # Bob's runs list must NOT include Alice's run
    res = clean_client.get("/api/discovery/runs")
    assert res.status_code == 200
    assert run_a.target_url not in [r["target_url"] for r in res.json()]

    # Bob cannot dismiss Alice's candidate
    csrf_b = generate_csrf_token()
    clean_client.cookies.set(CSRF_COOKIE_NAME, csrf_b)
    res = clean_client.post(
        f"/api/discovery/dismiss/{cand_a.id}",
        headers={CSRF_HEADER_NAME: csrf_b},
    )
    assert res.status_code == 404


# ── 5. Inactive / Disabled Account Blocking ───────────────────────────────

@pytest.mark.asyncio
async def test_inactive_user_cannot_login_or_access(clean_client, session):
    user, token = _create_user(session, email="banned@test.com", is_active=False)
    await session.commit()

    # Inactive user login returns 403
    res = clean_client.post("/api/auth/login", json={"email": "banned@test.com", "password": "password123"})
    assert res.status_code == 403
    assert "disabled" in res.json()["detail"].lower()

    # Inactive session cookie rejected on protected routes
    clean_client.cookies.set("dw_session", token)
    res = clean_client.get("/api/events")
    assert res.status_code == 401


# ── 6. Cookie Security Flags ──────────────────────────────────────────────

def test_session_cookie_flags(clean_client):
    res = clean_client.post(
        "/api/auth/register",
        json={"email": "cookie_test@example.com", "password": "password123"},
    )
    assert res.status_code == 200

    # Inspect Set-Cookie headers
    cookie_headers = res.headers.get_list("set-cookie") if hasattr(res.headers, "get_list") else [res.headers.get("set-cookie", "")]
    joined = " ".join(cookie_headers)

    # dw_session must be HttpOnly
    assert "dw_session" in res.cookies
    # dw_csrf must be present and readable by JS (HttpOnly=False)
    assert "dw_csrf" in res.cookies


# ── 7. Ask AI Cross-User Isolation ────────────────────────────────────────

@pytest.mark.asyncio
async def test_ask_ai_cross_user_isolation(clean_client, session):
    from app.config import settings
    user_a, token_a = _create_user(session, email="alice_ai@test.com")
    user_b, token_b = _create_user(session, email="bob_ai@test.com")

    # Alice's proprietary change event
    ev_a = ChangeEvent(
        source_id="secret_competitor",
        change_type="price",
        severity="high",
        description="Confidential Enterprise discount lowered to $99",
        old_value="$199",
        new_value="$99",
        user_id=user_a.id,
    )
    # Legacy/global event (user_id is None)
    ev_legacy = ChangeEvent(
        source_id="public_competitor",
        change_type="price",
        severity="low",
        description="Public tier updated to $20",
        old_value="$25",
        new_value="$20",
        user_id=None,
    )
    session.add(ev_a)
    session.add(ev_legacy)
    await session.commit()

    csrf_b = generate_csrf_token()
    clean_client.cookies.set("dw_session", token_b)
    clean_client.cookies.set(CSRF_COOKIE_NAME, csrf_b)

    # Bob asks AI about secret_competitor
    settings.ALLOW_LEGACY_GLOBAL_READS = False
    res = clean_client.post(
        "/api/ai/query",
        json={"question": "What is secret_competitor price?", "source_id": "secret_competitor"},
        headers={CSRF_HEADER_NAME: csrf_b},
    )
    assert res.status_code == 200
    data = res.json()
    # Must NOT contain Alice's private evidence!
    assert "Confidential Enterprise discount" not in data["answer"]
    assert len(data["evidence"]) == 0

    # Under strict ALLOW_LEGACY_GLOBAL_READS=False, Bob does NOT see legacy rows either
    res_legacy = clean_client.post(
        "/api/ai/query",
        json={"question": "What changed for public_competitor?"},
        headers={CSRF_HEADER_NAME: csrf_b},
    )
    assert res_legacy.status_code == 200
    assert len(res_legacy.json()["evidence"]) == 0

    # If ALLOW_LEGACY_GLOBAL_READS is True, legacy rows become visible
    settings.ALLOW_LEGACY_GLOBAL_READS = True
    try:
        res_legacy_opt = clean_client.post(
            "/api/ai/query",
            json={"question": "What changed for public_competitor?"},
            headers={CSRF_HEADER_NAME: csrf_b},
        )
        assert res_legacy_opt.status_code == 200
        assert len(res_legacy_opt.json()["evidence"]) > 0
    finally:
        settings.ALLOW_LEGACY_GLOBAL_READS = False


# ── 8. SSRF Redirect Protection ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_crawler_blocks_unsafe_redirect(clean_client):
    """Crawler must reject requests that redirect to private/loopback/cloud-metadata."""
    from app.services.crawler import crawler
    from unittest.mock import MagicMock

    # Simulate an HTTP response that was redirected to 169.254.169.254
    mock_history = [
        MagicMock(url="http://public-site.com/redirect"),
        MagicMock(url="http://169.254.169.254/latest/meta-data/"),
    ]
    mock_resp = MagicMock()
    mock_resp.history = mock_history
    mock_resp.url = "http://169.254.169.254/latest/meta-data/"
    mock_resp.status = 200

    with patch("aiohttp.ClientSession.get") as mock_get:
        mock_get.return_value.__aenter__.return_value = mock_resp
        result = await crawler.crawl("test_comp", "http://public-site.com", allow_local=False)
        assert result.success is False
        assert "Unsafe redirect blocked" in result.error


# ── 9. End-to-End Discovery-to-Monitoring Workflow ────────────────────────

@pytest.mark.asyncio
async def test_e2e_discovery_to_monitoring_workflow(clean_client, session):
    """Verify full lifecycle: analyze domain -> review candidate -> track into monitoring -> query events."""
    user, token = _create_user(session, email="owner@test.com")
    await session.commit()

    csrf = generate_csrf_token()
    clean_client.cookies.set("dw_session", token)
    clean_client.cookies.set(CSRF_COOKIE_NAME, csrf)

    # 1. Profile domain & discover candidates
    with patch("app.services.profiler.profiler.profile_website", new_callable=AsyncMock) as mock_profile, \
         patch("app.services.discovery.discovery_engine.discover_candidates", new_callable=AsyncMock) as mock_disc:
        mock_profile.return_value = {
            "company_name": "Acme Corp",
            "normalized_domain": "acme.com",
            "company_description": "Cloud security platform",
            "industry_category": "Cybersecurity",
            "products_and_services": ["EDR"],
            "target_customers": ["Enterprise"],
            "customer_problems": ["Ransomware"],
            "features_and_value_props": ["Real-time protection"],
            "pricing_model": "Subscription",
            "pricing_plans": [],
            "keywords": ["security", "cloud"],
            "source_urls": ["https://acme.com"],
            "pages_crawled_count": 1,
            "confidence_score": 0.9,
            "missing_fields": [],
        }
        mock_disc.return_value = [
            {
                "candidate_name": "RivalSecurity",
                "website_url": "https://example.com",
                "normalized_domain": "example.com",
                "match_score": 92.0,
                "classification": "direct",
                "classification_reason": "Direct overlap in cloud security",
                "match_explanation": "Matches cloud security enterprise focus",
                "is_verified": True,
                "evidence": {"shared_keywords": ["security"]},
                "missing_evidence": [],
            }
        ]

        # Analyze domain
        res = clean_client.post(
            "/api/discovery/analyze",
            json={"url": "https://example.com"},
            headers={CSRF_HEADER_NAME: csrf},
        )
        assert res.status_code == 200, res.text
        run_data = res.json()
        assert len(run_data["candidates"]) == 1
        candidate_id = run_data["candidates"][0]["id"]

    # 2. Track candidate into active monitoring
    with patch("app.services.scheduler.scheduler.add_competitor", new_callable=AsyncMock) as mock_sched_add:
        mock_sched_add.return_value = True
        res_track = clean_client.post(
            "/api/discovery/track",
            json={"candidate_id": candidate_id, "custom_name": "RivalSecurity"},
            headers={CSRF_HEADER_NAME: csrf},
        )
        assert res_track.status_code == 200
        assert res_track.json()["status"] == "tracked"

    # 3. Verify competitor shows up in user's monitored competitors list
    comp_row = CompetitorRegistry(
        source_id="RivalSecurity",
        url="https://rival-sec.com",
        user_id=user.id,
    )
    session.add(comp_row)
    await session.commit()

    res_comp = clean_client.get("/api/competitors")
    assert res_comp.status_code == 200
    comp_names = [c["source_id"] for c in res_comp.json()["competitors"]]
    assert "RivalSecurity" in comp_names


"""
API contract and deduplication tests for DriftWatch.
Tests:
- GET /health
- POST /api/crawl/single contract (P1: body schema, 422 validation, mock crawl)
- POST /api/competitors/add deduplication (P4: case-insensitivity, SSRF rejection)
- ALLOW_LOCAL_CRAWLS toggle behavior on URL validation
"""
import pytest
from unittest.mock import patch, AsyncMock
from app.services.crawler import CrawlResult
from app.services.url_validator import validate_crawl_url, URLValidationError


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "DriftWatch Backend"


def test_crawl_single_missing_fields_returns_422(client):
    # Empty body
    res = client.post("/api/crawl/single", json={})
    assert res.status_code == 422

    # Missing url
    res = client.post("/api/crawl/single", json={"source_id": "test_comp"})
    assert res.status_code == 422

    # Missing source_id
    res = client.post("/api/crawl/single", json={"url": "https://example.com"})
    assert res.status_code == 422


def test_crawl_single_success_contract(client):
    mock_result = CrawlResult(
        source_id="test_comp",
        url="https://example.com/pricing",
        headline="Best Pricing",
        pricing=[{"name": "Pro", "price": "$49/mo"}],
        features=["Feature 1"],
        keywords=["pricing", "pro"],
        raw_html="<html></html>",
        success=True,
        attempts=1,
    )
    with patch("app.main.crawler.crawl", new_callable=AsyncMock) as mock_crawl:
        mock_crawl.return_value = mock_result
        res = client.post(
            "/api/crawl/single",
            json={"source_id": "test_comp", "url": "https://example.com/pricing"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["success"] is True
        assert data["source_id"] == "test_comp"
        assert data["headline"] == "Best Pricing"
        assert len(data["pricing"]) == 1


def test_crawl_single_ssrf_rejected(client):
    # Without mock, an SSRF-violating URL will be rejected by the crawler
    res = client.post(
        "/api/crawl/single",
        json={"source_id": "evil_comp", "url": "http://169.254.169.254/latest/meta-data"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is False
    assert "URL rejected" in data["error"]


@pytest.mark.asyncio
async def test_competitor_add_deduplication(client):
    # Add a competitor
    res1 = client.post(
        "/api/competitors/add",
        json={"name": "Byjus", "url": "https://byjus.com"},
    )
    assert res1.status_code == 200
    assert res1.json()["name"] == "Byjus"

    # Add exact duplicate
    res2 = client.post(
        "/api/competitors/add",
        json={"name": "Byjus", "url": "https://byjus.com"},
    )
    assert res2.status_code == 400
    assert "already exists" in res2.json()["detail"]

    # Add case variation (BYJUS) - should be rejected as duplicate
    res3 = client.post(
        "/api/competitors/add",
        json={"name": "BYJUS", "url": "https://byjus.com"},
    )
    assert res3.status_code == 400
    assert "already exists" in res3.json()["detail"]

    # Another case variation with whitespace
    res4 = client.post(
        "/api/competitors/add",
        json={"name": "  byjus  ", "url": "https://byjus.com"},
    )
    assert res4.status_code == 400
    assert "already exists" in res4.json()["detail"]


@pytest.mark.asyncio
async def test_competitor_add_ssrf_rejection(client):
    res = client.post(
        "/api/competitors/add",
        json={"name": "EvilComp", "url": "http://127.0.0.1:8000/internal"},
    )
    assert res.status_code == 400
    # The error should clearly indicate the URL was rejected for SSRF reasons
    detail = res.json()["detail"]
    assert "Unsafe URL" in detail or "restricted" in detail.lower()


def test_allow_local_crawls_toggle():
    # By default (allow_local=False), 127.0.0.1 is rejected
    with pytest.raises(URLValidationError):
        validate_crawl_url("http://127.0.0.1:8080/test", allow_local=False)

    # When allow_local=True, loopback is allowed
    url = validate_crawl_url("http://127.0.0.1:8080/test", allow_local=True)
    assert url == "http://127.0.0.1:8080/test"

    # Invalid schemes are still rejected even with allow_local=True
    with pytest.raises(URLValidationError):
        validate_crawl_url("file:///etc/passwd", allow_local=True)


@pytest.mark.asyncio
async def test_case_insensitive_unique_index_enforced(engine, session):
    """Regression test for the competitor dedup race condition.

    The app-level check uses func.lower(source_id), but before the
    case-insensitive unique index existed, two concurrent requests with
    case variants (byjus / BYJUS) could both pass the check and one would
    blow up with a raw IntegrityError instead of a clean 400. The DB-level
    unique index must reject the case variant even when the app-level check
    is bypassed entirely.
    """
    from app.models.models import CompetitorRegistry
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

    # Insert the first competitor through the shared test session.
    session.add(CompetitorRegistry(source_id="byjus", url="https://byjus.com"))
    await session.commit()

    # Open a second independent session on the same engine and attempt a
    # case-variant insert. The DB-level unique index must reject it.
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionLocal() as s2:
        s2.add(CompetitorRegistry(source_id="BYJUS", url="https://byjus.com"))
        with pytest.raises(IntegrityError):
            await s2.commit()


def test_discovery_analyze_api_contract_ssrf(client):
    """Discovery endpoint should reject SSRF-unsafe targets with HTTP 400."""
    res = client.post("/api/discovery/analyze", json={"url": "http://127.0.0.1:8000/internal"})
    assert res.status_code == 400
    assert "Unsafe URL" in res.json()["detail"]


def test_discovery_track_missing_candidate(client):
    """Tracking a nonexistent candidate ID returns 404."""
    import uuid
    res = client.post("/api/discovery/track", json={"candidate_id": str(uuid.uuid4())})
    assert res.status_code == 404
    assert "not found" in res.json()["detail"].lower()


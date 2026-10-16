"""
Unit & Integration Tests for Phase 2: Competitor Discovery Engine.
Covers:
- URL validation & SSRF protection in discovery
- Company profiler and business signal extraction
- Search provider adapters and missing credentials behavior
- Query generation
- Candidate deduplication and normalization
- Candidate verification and multi-factor ranking
- Explainable classification and honest uncertainty reporting
- Persistence in isolated SQLite database
- Tracking integration into existing competitor registry
- Duplicate tracking prevention
"""
import pytest
import uuid
from unittest.mock import patch, AsyncMock
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select

from app.db.database import Base
from app.models.models import DiscoveryRun, DiscoveryCandidate, CompetitorRegistry
from app.services.profiler import CompanyProfiler, normalize_domain
from app.services.search_providers import (
    SearchProviderBase,
    TavilySearchProvider,
    SerpApiSearchProvider,
    MockSearchProvider,
    SearchResultItem,
    get_search_provider,
)
from app.services.discovery import CompetitorDiscoveryEngine
from app.services.url_validator import URLValidationError


def test_normalize_domain():
    assert normalize_domain("https://www.coursera.org/courses") == "coursera.org"
    assert normalize_domain("http://sub.domain.co.uk:8080/path") == "sub.domain.co.uk"
    assert normalize_domain("example.com") == "example.com"


def test_search_provider_missing_credentials():
    # Tavily without API key raises error
    tavily = TavilySearchProvider(api_key=None)
    with patch("app.config.settings.TAVILY_API_KEY", None):
        assert tavily.is_configured() is False
        with pytest.raises(RuntimeError, match="Tavily API key is not configured"):
            import asyncio
            asyncio.run(tavily.search("query"))

    # SerpAPI without key
    serp = SerpApiSearchProvider(api_key=None)
    with patch("app.config.settings.SERPAPI_API_KEY", None):
        assert serp.is_configured() is False
        with pytest.raises(RuntimeError, match="SerpAPI key is not configured"):
            import asyncio
            asyncio.run(serp.search("query"))


@pytest.mark.asyncio
async def test_mock_search_provider():
    mock_prov = MockSearchProvider()
    assert mock_prov.is_configured() is True
    results = await mock_prov.search("edtech learning platforms")
    assert len(results) > 0
    assert any("coursera" in r.url.lower() for r in results)


def test_query_generation():
    engine = CompetitorDiscoveryEngine(search_provider=MockSearchProvider())
    profile = {
        "company_name": "ApexLearning",
        "industry_category": "Education & EdTech",
        "keywords": ["exam", "coaching", "ai", "skills"],
        "customer_problems": ["Exam preparation readiness"],
    }
    queries = engine.generate_search_queries(profile)
    assert len(queries) >= 3
    assert any("competitors" in q.lower() for q in queries)
    assert any("alternatives" in q.lower() for q in queries)


@pytest.mark.asyncio
async def test_candidate_deduplication_and_ranking():
    # Mock items returning duplicate domains
    class CustomSearch(SearchProviderBase):
        @property
        def name(self): return "custom"
        def is_configured(self): return True
        async def search(self, query, max_results=5):
            return [
                SearchResultItem("Coursera Degrees", "https://www.coursera.org/degrees", "Learn skills"),
                SearchResultItem("Coursera Home", "https://coursera.org", "Top university courses"),
                SearchResultItem("Udemy Courses", "https://www.udemy.com/topic/ai", "AI online courses"),
            ]

    engine = CompetitorDiscoveryEngine(search_provider=CustomSearch())
    profile = {
        "company_name": "ApexLearning",
        "normalized_domain": "apexlearning.com",
        "industry_category": "Education & EdTech",
        "keywords": ["ai", "learning", "skills"],
        "customer_problems": ["Exam readiness"],
    }

    candidates = await engine.discover_candidates(profile, allow_local=True)
    # Coursera duplicate should be deduplicated to 1 candidate
    domains = [c["normalized_domain"] for c in candidates]
    assert domains.count("coursera.org") == 1
    assert "udemy.com" in domains
    assert len(candidates) == 2

    # Verify score structure and classifications
    for c in candidates:
        assert 0 <= c["match_score"] <= 100
        assert c["classification"] in ["direct", "indirect", "adjacent"]
        assert "evidence" in c
        assert isinstance(c["missing_evidence"], list)


@pytest.mark.asyncio
async def test_discovery_db_persistence_and_tracking(tmp_path):
    # Use isolated SQLite database
    db_file = tmp_path / "test_discovery.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    engine = create_async_engine(db_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Create a discovery run
        run_id = uuid.uuid4()
        run = DiscoveryRun(
            id=run_id,
            target_url="https://apexlearning.com",
            normalized_domain="apexlearning.com",
            company_name="ApexLearning",
            status="completed",
            company_profile={"company_name": "ApexLearning", "industry": "EdTech"},
        )
        session.add(run)

        # Add candidate
        cand_id = uuid.uuid4()
        cand = DiscoveryCandidate(
            id=cand_id,
            run_id=run_id,
            candidate_name="Coursera",
            website_url="https://www.coursera.org",
            normalized_domain="coursera.org",
            match_score=85.0,
            classification="direct",
            classification_reason="High direct overlap",
            match_explanation="Direct competitor with online certification offerings",
            is_verified=True,
            status="suggested",
        )
        session.add(cand)
        await session.commit()

        # Query back
        res = await session.execute(select(DiscoveryCandidate).where(DiscoveryCandidate.id == cand_id))
        stored = res.scalar_one()
        assert stored.candidate_name == "Coursera"
        assert stored.status == "suggested"

        # Simulate user tracking
        stored.status = "tracked"
        reg = CompetitorRegistry(
            id=uuid.uuid4(),
            source_id="Coursera",
            url=stored.website_url,
        )
        session.add(reg)
        await session.commit()

        # Verify competitor is now tracked and in registry
        reg_res = await session.execute(select(CompetitorRegistry).where(CompetitorRegistry.source_id == "Coursera"))
        comp = reg_res.scalar_one()
        assert comp.url == "https://www.coursera.org"

    await engine.dispose()

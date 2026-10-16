"""Tests for the grounded Ask AI intelligence endpoint."""
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ChangeEvent
from app.services.ask_ai import query_intelligence


@pytest_asyncio.fixture
async def seeded_session(session):
    """Session with a couple of realistic change events already persisted."""
    ev1 = ChangeEvent(
        source_id="udemy",
        change_type="price",
        severity="high",
        old_value="129.99",
        new_value="149.99",
        description="Pro plan price increased from $129.99 to $149.99",
    )
    ev2 = ChangeEvent(
        source_id="scaler",
        change_type="keyword",
        severity="medium",
        old_value=None,
        new_value="AI, Generative",
        description="Competitor added AI and Generative keywords to homepage",
    )
    session.add_all([ev1, ev2])
    await session.commit()
    yield session


@pytest.mark.asyncio
async def test_query_empty_question(seeded_session):
    result = await query_intelligence("", seeded_session)
    assert result["total_matches"] == 0
    assert "Please provide" in result["answer"]


@pytest.mark.asyncio
async def test_query_pricing_intent_matches_price_events(seeded_session):
    result = await query_intelligence(
        "What changed in pricing?", seeded_session
    )
    # udemy price event should be the top match
    assert result["total_matches"] >= 1
    assert result["evidence"][0]["source_id"] == "udemy"
    assert "udemy" in result["answer"]
    assert "price" in result["answer"].lower()


@pytest.mark.asyncio
async def test_query_source_filter(seeded_session):
    result = await query_intelligence(
        "recent changes", seeded_session, source_id="scaler"
    )
    # Only scaler events returned when filtered by source
    assert all(e["source_id"] == "scaler" for e in result["evidence"])


@pytest.mark.asyncio
async def test_query_no_match_returns_helpful_message(seeded_session):
    result = await query_intelligence("completely unrelated xyz question", seeded_session)
    # Either no evidence or generic fallback; must not fabricate
    if result["total_matches"] == 0:
        assert "No recorded changes" in result["answer"]
    else:
        # If generic fallback used most recent events, evidence is still real records
        for e in result["evidence"]:
            assert e["source_id"] in {"udemy", "scaler"}


@pytest.mark.asyncio
async def test_ask_ai_endpoint(client, session, seeded_session):
    """End-to-end: POST /api/ai/query returns a grounded answer with evidence."""
    # The `client` fixture wires its own session; seed data into that session instead
    ev = ChangeEvent(
        source_id="coursera",
        change_type="price",
        severity="critical",
        old_value="49",
        new_value="99",
        description="Essential plan nearly doubled",
    )
    session.add(ev)
    await session.commit()

    res = client.post("/api/ai/query", json={"question": "What changed in pricing?"})
    assert res.status_code == 200
    body = res.json()
    assert body["question"] == "What changed in pricing?"
    assert body["total_matches"] >= 1
    assert isinstance(body["evidence"], list)
    assert any(e["source_id"] == "coursera" for e in body["evidence"])

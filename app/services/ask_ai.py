"""
Grounded intelligence query service for DriftWatch ("Ask AI").

Answers competitive intelligence questions using real data snapshots and
change events stored in the database, avoiding hallucinations by citing
exact database records as evidence.
"""
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import re

from app.models.models import ChangeEvent, DataSnapshot, PriceHistory


async def query_intelligence(
    question: str,
    db: AsyncSession,
    source_id: Optional[str] = None,
    limit: int = 15,
) -> Dict[str, Any]:
    """
    Search recorded intelligence and synthesize a grounded answer.

    Args:
        question: User query string
        db: Database async session
        source_id: Optional competitor filter
        limit: Max events to retrieve for grounding

    Returns:
        Dict with question, answer, evidence records, and matched competitor count.
    """
    cleaned_q = question.strip()
    if not cleaned_q:
        return {
            "question": question,
            "answer": "Please provide a question to query competitive intelligence.",
            "evidence": [],
            "total_matches": 0,
        }

    tokens = [w.lower() for w in re.findall(r"\w+", cleaned_q) if len(w) > 2]

    # Fetch recent change events
    stmt = select(ChangeEvent).order_by(desc(ChangeEvent.created_at)).limit(100)
    if source_id:
        stmt = stmt.where(ChangeEvent.source_id == source_id)

    res = await db.execute(stmt)
    all_events = res.scalars().all()

    # Score and filter events relevant to query tokens
    scored_events: List[tuple[int, ChangeEvent]] = []
    pricing_intent = any(k in cleaned_q.lower() for k in ["price", "pricing", "plan", "cost", "tier", "fee", "rate"])
    messaging_intent = any(k in cleaned_q.lower() for k in ["headline", "message", "messaging", "tagline", "positioning", "copy"])
    keyword_intent = any(k in cleaned_q.lower() for k in ["keyword", "feature", "term", "strategy", "ai", "skills"])

    for ev in all_events:
        score = 0
        desc_lower = (ev.description or "").lower()
        src_lower = (ev.source_id or "").lower()
        old_lower = (ev.old_value or "").lower()
        new_lower = (ev.new_value or "").lower()

        # Competitor name match
        if src_lower in cleaned_q.lower():
            score += 5

        # Type matches intent
        if pricing_intent and ev.change_type in ("price", "anomaly"):
            score += 3
        if messaging_intent and ev.change_type == "messaging":
            score += 3
        if keyword_intent and ev.change_type == "keyword":
            score += 3

        # Token overlap
        for t in tokens:
            if t in desc_lower or t in old_lower or t in new_lower or t in src_lower:
                score += 1

        if score > 0 or not tokens:
            scored_events.append((score, ev))

    # Sort by relevance score descending, then recency
    scored_events.sort(key=lambda pair: pair[0], reverse=True)
    top_events = [ev for _, ev in scored_events[:limit]]

    # If no specific events matched the keywords, take the most recent general events
    if not top_events and all_events:
        top_events = all_events[:5]

    evidence_list = [
        {
            "id": ev.id,
            "source_id": ev.source_id,
            "change_type": ev.change_type,
            "severity": ev.severity,
            "description": ev.description,
            "old_value": ev.old_value,
            "new_value": ev.new_value,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
        }
        for ev in top_events
    ]

    # Synthesize grounded answer
    if not evidence_list:
        answer = (
            f"No recorded changes or snapshots matched '{question}'. "
            "Trigger a crawl via /api/crawl to ingest fresh competitor data first."
        )
    else:
        competitors_seen = sorted(list({e["source_id"] for e in evidence_list}))
        types_seen = sorted(list({e["change_type"] for e in evidence_list}))

        bullets = []
        for e in evidence_list[:5]:
            bullets.append(
                f"- **{e['source_id']}** ({e['change_type']}, {e['severity']}): {e['description']}"
            )

        summary_intro = (
            f"Found {len(evidence_list)} relevant event(s) across {len(competitors_seen)} competitor(s) "
            f"({', '.join(competitors_seen)}):\n"
        )
        answer = summary_intro + "\n".join(bullets)

    return {
        "question": question,
        "answer": answer,
        "evidence": evidence_list,
        "total_matches": len(evidence_list),
    }

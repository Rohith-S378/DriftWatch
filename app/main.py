from fastapi import FastAPI, Depends, HTTPException
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional

from app.db.database import engine, Base, get_db
from app.routers import webhook
from app.models.models import ChangeEvent, DataSnapshot
from app.services.scheduler import init_scheduler, shutdown_scheduler, scheduler
from app.services.crawler import crawler
from app.models.schemas import ChangeEventOut, AskAIRequest, AskAIResponse, CrawlSingleRequest
from fastapi.middleware.cors import CORSMiddleware
import logging

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Start the background crawler scheduler
    await init_scheduler()
    yield
    # Shutdown
    await shutdown_scheduler()


app = FastAPI(
    title="DriftWatch — Competitive Intelligence Engine",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "DriftWatch Backend"}


@app.get("/api/events")
async def get_all_events(limit: int = 100, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChangeEvent).order_by(ChangeEvent.created_at.desc()).limit(limit)
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "source_id": e.source_id,
            "change_type": e.change_type,
            "severity": e.severity,
            "description": e.description,
            "old_value": e.old_value,
            "new_value": e.new_value,
            "diff": e.diff,
            "created_at": str(e.created_at),
        }
        for e in events
    ]


@app.get("/api/sources")
async def get_sources(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataSnapshot.source_id).distinct())
    return {"sources": result.scalars().all()}


@app.get("/api/events/{source_id}")
async def get_events_by_source(source_id: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ChangeEvent)
        .where(ChangeEvent.source_id == source_id)
        .order_by(ChangeEvent.created_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "source_id": e.source_id,
            "change_type": e.change_type,
            "severity": e.severity,
            "description": e.description,
            "old_value": e.old_value,
            "new_value": e.new_value,
            "diff": e.diff,
            "created_at": str(e.created_at),
        }
        for e in events
    ]


# NEW ENDPOINTS FOR CRAWLER & SCHEDULER

class CompetitorRequest(BaseModel):
    name: str
    url: str


@app.post("/api/competitors/add")
async def add_competitor(req: CompetitorRequest):
    """Add a competitor for auto-crawling.

    The scheduler returns False for two *different* failure modes: a genuine
    duplicate name, and an SSRF-unsafe URL. Previously both were reported as
    "already exists", which made a blocked local-crawl URL look like a duplicate.
    Distinguish them so the caller gets an actionable error.
    """
    from app.services.url_validator import URLValidationError
    from app.config import settings

    try:
        from app.services.url_validator import validate_crawl_url
        validate_crawl_url(req.url, allow_local=settings.ALLOW_LOCAL_CRAWLS)
    except URLValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Unsafe URL: {exc}") from exc

    success = await scheduler.add_competitor(req.name, req.url)
    if not success:
        raise HTTPException(status_code=400, detail=f"Competitor '{req.name}' already exists")
    return {"status": "added", "name": req.name, "url": req.url}


@app.get("/api/competitors")
async def list_competitors():
    """List all registered competitors."""
    competitors = await scheduler.list_competitors()
    return {"competitors": competitors}


@app.delete("/api/competitors/{name}")
async def remove_competitor(name: str):
    """Remove a competitor from auto-crawling."""
    success = await scheduler.remove_competitor(name)
    if not success:
        raise HTTPException(status_code=404, detail="Competitor not found")
    return {"status": "removed", "name": name}


@app.post("/api/crawl/trigger")
async def trigger_crawl(source_id: Optional[str] = None):
    """
    Trigger immediate crawl.
    If source_id provided, crawl only that competitor.
    Otherwise, crawl all registered competitors.
    """
    results = await scheduler.crawl_now(source_id)
    return {
        "crawled": len(results),
        "results": [
            {
                "source_id": r.source_id,
                "success": r.success,
                "headline": r.headline,
                "pricing_found": len(r.pricing),
                "error": r.error
            }
            for r in results
        ]
    }


@app.post("/api/crawl/single")
async def crawl_single(req: CrawlSingleRequest, db: AsyncSession = Depends(get_db)):
    """Crawl a single URL and persist the snapshot so it shows up in
    Insights/Changes immediately (previously this crawled but never saved)."""
    from app.models.schemas import WebhookPayload
    from app.services.snapshot_service import process_webhook
    from app.config import settings

    result = await crawler.crawl(
        source_id=req.source_id,
        url=req.url,
        allow_local=settings.ALLOW_LOCAL_CRAWLS,
    )

    if result.success:
        payload = WebhookPayload(
            source_id=result.source_id,
            source_type="pricing",
            data={
                "headline": result.headline,
                "plans": result.pricing,
                "keywords": result.keywords,
                "features": result.features,
                "crawled_url": result.url,
            },
        )
        await process_webhook(payload, db)

    return {
        "source_id": result.source_id,
        "url": result.url,
        "success": result.success,
        "headline": result.headline,
        "pricing": result.pricing,
        "keywords": result.keywords,
        "features": result.features,
        "error": result.error
    }


@app.post("/api/ai/query", response_model=AskAIResponse)
async def ask_ai(req: AskAIRequest, db: AsyncSession = Depends(get_db)):
    """Grounded intelligence Q&A: query real events and snapshots."""
    from app.services.ask_ai import query_intelligence
    result = await query_intelligence(req.question, db, source_id=req.source_id)
    return result


@app.get("/api/ai/query", response_model=AskAIResponse)
async def ask_ai_get(question: str, source_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """GET variant for lightweight browser/curl queries."""
    from app.services.ask_ai import query_intelligence
    result = await query_intelligence(question, db, source_id=source_id)
    return result


# ── COMPETITOR DISCOVERY ENGINE API ──────────────────────────────────────────

from app.models.models import DiscoveryRun, DiscoveryCandidate
from app.models.schemas import (
    DiscoveryAnalyzeRequest,
    DiscoveryRunOut,
    DiscoveryCandidateOut,
    TrackCandidateRequest,
)
from app.services.profiler import profiler, normalize_domain
from app.services.discovery import discovery_engine
from app.services.url_validator import validate_crawl_url, URLValidationError
from app.config import settings
import uuid


@app.post("/api/discovery/analyze")
async def analyze_and_discover(req: DiscoveryAnalyzeRequest, db: AsyncSession = Depends(get_db)):
    """
    Profile a company website and execute competitor discovery.
    Produces structured company profile, discovers candidate competitors,
    ranks and classifies them with explainable evidence, and persists the run.
    """
    # 1. URL Safety and SSRF check
    try:
        safe_url = validate_crawl_url(req.url, allow_local=settings.ALLOW_LOCAL_CRAWLS)
    except URLValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Unsafe URL: {exc}")

    domain = normalize_domain(safe_url)

    # 2. Extract company profile
    try:
        profile = await profiler.profile_website(safe_url, allow_local=settings.ALLOW_LOCAL_CRAWLS)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to profile website: {exc}")

    # 3. Create DiscoveryRun record
    run_id = uuid.uuid4()
    run = DiscoveryRun(
        id=run_id,
        target_url=safe_url,
        normalized_domain=domain,
        company_name=profile["company_name"],
        status="completed",
        company_profile=profile,
    )
    db.add(run)

    # 4. Discover, verify, score & rank candidate competitors
    try:
        raw_candidates = await discovery_engine.discover_candidates(
            profile=profile,
            allow_local=settings.ALLOW_LOCAL_CRAWLS,
            max_candidates=settings.DISCOVERY_MAX_CANDIDATES,
        )
    except Exception as exc:
        run.status = "failed"
        run.error = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Discovery failed: {exc}")

    # 5. Persist candidates
    candidate_entities = []
    for cand in raw_candidates:
        cand_id = uuid.uuid4()
        c_entity = DiscoveryCandidate(
            id=cand_id,
            run_id=run_id,
            candidate_name=cand["candidate_name"],
            website_url=cand["website_url"],
            normalized_domain=cand["normalized_domain"],
            match_score=cand["match_score"],
            classification=cand["classification"],
            classification_reason=cand.get("classification_reason"),
            match_explanation=cand["match_explanation"],
            is_verified=cand["is_verified"],
            evidence=cand.get("evidence"),
            missing_evidence=cand.get("missing_evidence"),
            status="suggested",
        )
        db.add(c_entity)
        candidate_entities.append(c_entity)

    await db.commit()

    return {
        "id": str(run.id),
        "target_url": run.target_url,
        "normalized_domain": run.normalized_domain,
        "company_name": run.company_name,
        "status": run.status,
        "company_profile": run.company_profile,
        "candidates": [
            {
                "id": str(c.id),
                "candidate_name": c.candidate_name,
                "website_url": c.website_url,
                "normalized_domain": c.normalized_domain,
                "match_score": c.match_score,
                "classification": c.classification,
                "classification_reason": c.classification_reason,
                "match_explanation": c.match_explanation,
                "is_verified": c.is_verified,
                "evidence": c.evidence,
                "missing_evidence": c.missing_evidence,
                "status": c.status,
                "created_at": str(c.created_at),
            }
            for c in candidate_entities
        ],
        "created_at": str(run.created_at),
    }


@app.get("/api/discovery/runs")
async def list_discovery_runs(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """List past discovery runs."""
    res = await db.execute(
        select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(limit)
    )
    runs = res.scalars().all()
    return [
        {
            "id": str(r.id),
            "target_url": r.target_url,
            "normalized_domain": r.normalized_domain,
            "company_name": r.company_name,
            "status": r.status,
            "company_profile": r.company_profile,
            "created_at": str(r.created_at),
        }
        for r in runs
    ]


@app.get("/api/discovery/runs/{run_id}")
async def get_discovery_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Get details and candidates of a specific discovery run."""
    try:
        parsed_id = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run ID format")

    run_res = await db.execute(select(DiscoveryRun).where(DiscoveryRun.id == parsed_id))
    run = run_res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Discovery run not found")

    cand_res = await db.execute(
        select(DiscoveryCandidate)
        .where(DiscoveryCandidate.run_id == parsed_id)
        .order_by(DiscoveryCandidate.match_score.desc())
    )
    candidates = cand_res.scalars().all()

    return {
        "id": str(run.id),
        "target_url": run.target_url,
        "normalized_domain": run.normalized_domain,
        "company_name": run.company_name,
        "status": run.status,
        "company_profile": run.company_profile,
        "candidates": [
            {
                "id": str(c.id),
                "candidate_name": c.candidate_name,
                "website_url": c.website_url,
                "normalized_domain": c.normalized_domain,
                "match_score": c.match_score,
                "classification": c.classification,
                "classification_reason": c.classification_reason,
                "match_explanation": c.match_explanation,
                "is_verified": c.is_verified,
                "evidence": c.evidence,
                "missing_evidence": c.missing_evidence,
                "status": c.status,
                "created_at": str(c.created_at),
            }
            for c in candidates
        ],
        "created_at": str(run.created_at),
    }


@app.post("/api/discovery/track")
async def track_candidate(req: TrackCandidateRequest, db: AsyncSession = Depends(get_db)):
    """
    Track a discovered competitor candidate into the monitoring pipeline.
    Reuses existing competitor registry and crawler scheduling.
    """
    cand_res = await db.execute(select(DiscoveryCandidate).where(DiscoveryCandidate.id == req.candidate_id))
    candidate = cand_res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    competitor_name = (req.custom_name or candidate.candidate_name).strip()
    competitor_url = candidate.website_url.strip()

    # Re-validate target URL
    try:
        validate_crawl_url(competitor_url, allow_local=settings.ALLOW_LOCAL_CRAWLS)
    except URLValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Unsafe candidate URL: {exc}")

    # Register into existing competitor monitoring scheduler
    success = await scheduler.add_competitor(competitor_name, competitor_url)
    if not success:
        raise HTTPException(status_code=400, detail=f"Competitor '{competitor_name}' is already being monitored")

    candidate.status = "tracked"
    await db.commit()

    return {
        "status": "tracked",
        "candidate_id": str(candidate.id),
        "competitor_name": competitor_name,
        "url": competitor_url,
    }


@app.post("/api/discovery/dismiss/{candidate_id}")
async def dismiss_candidate(candidate_id: str, db: AsyncSession = Depends(get_db)):
    """Dismiss a discovered competitor candidate."""
    try:
        parsed_id = uuid.UUID(candidate_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid candidate ID format")

    cand_res = await db.execute(select(DiscoveryCandidate).where(DiscoveryCandidate.id == parsed_id))
    candidate = cand_res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")

    candidate.status = "dismissed"
    await db.commit()

    return {"status": "dismissed", "candidate_id": str(candidate.id)}
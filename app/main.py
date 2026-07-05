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
from app.services.crawler import crawl_competitor
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
    title="Sirius Market Intelligence Engine",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "Sirius Backend"}


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
    """Add a competitor for auto-crawling."""
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
async def crawl_single(source_id: str, url: str, db: AsyncSession = Depends(get_db)):
    """Crawl a single URL and persist the snapshot so it shows up in
    Insights/Changes immediately (previously this crawled but never saved)."""
    from app.models.schemas import WebhookPayload
    from app.services.snapshot_service import process_webhook

    result = await crawl_competitor(source_id, url)

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
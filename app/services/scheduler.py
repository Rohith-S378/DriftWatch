"""
Background scheduler for automated competitor crawling.
Runs crawls every N hours and ingests results automatically.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from typing import Dict, List, Optional
import asyncio
import logging

from app.services.crawler import crawl_multiple, CrawlResult
from app.services.snapshot_service import process_webhook
from app.db.database import async_session
from app.models.models import CompetitorRegistry

logger = logging.getLogger(__name__)


class CrawlScheduler:
    """Manages scheduled crawling of competitor websites."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False

    async def start(self):
        """Start the scheduler with auto-crawl every 6 hours."""
        if self.is_running:
            return

        self.scheduler.add_job(
            self._scheduled_crawl,
            trigger=IntervalTrigger(hours=6),
            id="auto_crawl",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info("Crawl scheduler started (every 6 hours)")

    async def stop(self):
        """Stop the scheduler."""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Crawl scheduler stopped")

    async def _get_competitors_from_db(self) -> List[Dict[str, str]]:
        """Fetch all competitors from the database."""
        async with async_session() as session:
            result = await session.execute(
                select(CompetitorRegistry.source_id, CompetitorRegistry.url)
            )
            competitors = [
                {"source_id": row.source_id, "url": row.url}
                for row in result.all()
            ]
            return competitors

    async def _scheduled_crawl(self):
        """Execute scheduled crawl of all registered competitors."""
        competitors = await self._get_competitors_from_db()
        if not competitors:
            logger.info("No competitors registered for auto-crawl")
            return

        logger.info(f"Starting scheduled crawl of {len(competitors)} competitors")

        results = await crawl_multiple(competitors)

        # Process results and ingest to database
        async with async_session() as session:
            for result in results:
                if result.success:
                    await self._ingest_crawl_result(result, session)
                    logger.info(f"Successfully crawled and ingested: {result.source_id}")
                else:
                    logger.error(f"Failed to crawl {result.source_id}: {result.error}")

    async def _ingest_crawl_result(self, result: CrawlResult, session: AsyncSession):
        """Convert crawl result to webhook payload and process."""
        from app.models.schemas import WebhookPayload

        payload = WebhookPayload(
            source_id=result.source_id,
            source_type="pricing",  # Could be more specific
            data={
                "headline": result.headline,
                "plans": result.pricing,
                "keywords": result.keywords,
                "features": result.features,
                "crawled_url": result.url,
            }
        )

        await process_webhook(payload, session)

    async def add_competitor(self, name: str, url: str,
                            headline_selector: Optional[str] = None,
                            price_selector: Optional[str] = None,
                            feature_selector: Optional[str] = None,
                            keyword_extraction: bool = True,
                            allow_local: bool = False) -> bool:
        """
        Register a competitor for auto-crawling.

        Args:
            name: Unique identifier for competitor
            url: URL to crawl
            headline_selector: CSS selector for headline (optional)
            price_selector: CSS selector for pricing plans (optional)
            feature_selector: CSS selector for features (optional)
            keyword_extraction: Whether to extract keywords from text (default True)

        Returns:
            True if added, False if name already exists or URL fails SSRF safety check
        """
        from app.services.url_validator import validate_crawl_url, URLValidationError
        from app.config import settings

        # SSRF-safe URL validation
        try:
            validate_crawl_url(url, allow_local=allow_local or settings.ALLOW_LOCAL_CRAWLS)
        except URLValidationError as exc:
            logger.warning(f"Rejecting competitor {name}: invalid or unsafe URL '{url}': {exc}")
            return False
        clean_name = name.strip()
        async with async_session() as session:
            # Check if competitor already exists (case-insensitive)
            result = await session.execute(
                select(CompetitorRegistry).where(
                    func.lower(CompetitorRegistry.source_id) == clean_name.lower()
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return False

            # Create new competitor registry entry
            competitor = CompetitorRegistry(
                source_id=clean_name,
                url=url.strip(),
                headline_selector=headline_selector,
                price_selector=price_selector,
                feature_selector=feature_selector,
                keyword_extraction=keyword_extraction
            )
            session.add(competitor)
            try:
                await session.commit()
            except IntegrityError:
                # Race condition: a concurrent request inserted a competitor
                # that collides on the case-insensitive unique index between
                # our app-level check and this commit. Treat it as a duplicate.
                await session.rollback()
                logger.warning(f"Competitor '{clean_name}' collided on insert (duplicate)")
                return False
            logger.info(f"Added competitor: {clean_name} -> {url}")
            return True

    async def remove_competitor(self, name: str) -> bool:
        """Remove a competitor from auto-crawl."""
        clean_name = name.strip()
        async with async_session() as session:
            result = await session.execute(
                select(CompetitorRegistry).where(
                    func.lower(CompetitorRegistry.source_id) == clean_name.lower()
                )
            )
            competitor = result.scalar_one_or_none()
            if not competitor:
                return False
            await session.delete(competitor)
            await session.commit()
            logger.info(f"Removed competitor: {clean_name}")
            return True

    async def list_competitors(self) -> List[Dict[str, str]]:
        """List all registered competitors."""
        return await self._get_competitors_from_db()

    async def crawl_now(self, source_id: str = None) -> List[CrawlResult]:
        """
        Trigger immediate crawl.

        Args:
            source_id: Specific competitor to crawl, or None for all

        Returns:
            List of crawl results
        """
        competitors = await self._get_competitors_from_db()
        if source_id:
            # Filter to specific competitor
            competitors = [c for c in competitors if c["source_id"] == source_id]
            if not competitors:
                return []
        # If no competitors after filtering (and source_id was specified), return empty
        if not competitors:
            return []

        results = await crawl_multiple(competitors)

        # Ingest results
        async with async_session() as session:
            for result in results:
                if result.success:
                    await self._ingest_crawl_result(result, session)

        return results


# Global scheduler instance
scheduler = CrawlScheduler()


async def init_scheduler():
    """Initialize and start the scheduler."""
    await scheduler.start()


async def shutdown_scheduler():
    """Shutdown the scheduler."""
    await scheduler.stop()

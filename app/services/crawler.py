"""
Active web crawler for competitor intelligence.
Fetches competitor websites, extracts pricing, messaging, and features.
Supports both static HTTP fetch and optional Playwright browser rendering for JS-heavy sites.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
import re
import logging

from app.services.url_validator import validate_crawl_url, URLValidationError

logger = logging.getLogger(__name__)

# Maximum number of attempts per crawl (initial + retries).
MAX_ATTEMPTS = 3
# Base delay in seconds between retries (exponential backoff: 1s, 2s, 4s...).
RETRY_BASE_DELAY = 1.0
# HTTP status codes that are worth retrying (transient).
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}

# Browser rendering settings
BROWSER_NAVIGATION_TIMEOUT = 15000  # 15 seconds
BROWSER_CONTENT_TIMEOUT = 30000  # 30 seconds total


@dataclass
class CrawlResult:
    source_id: str
    url: str
    headline: str
    pricing: List[Dict[str, Any]]
    features: List[str]
    keywords: List[str]
    raw_html: str
    success: bool
    error: Optional[str] = None
    attempts: int = 0
    browser_rendered: bool = field(default=False, init=False)


class CompetitorCrawler:
    """Crawls competitor websites and extracts structured data."""

    # Common CSS selectors for pricing pages
    PRICE_SELECTORS = [
        ".pricing-plan", ".plan", "[class*='price']", "[class*='plan']",
        ".tier", ".package", "[class*='tier']", "[class*='package']",
        "#pricing .plan", ".pricing-table tr", ".subscription-option"
    ]

    HEADLINE_SELECTORS = [
        "h1", ".hero h1", ".headline", "[class*='headline']",
        ".title", "[class*='title']", ".tagline", "[class*='tagline']"
    ]

    FEATURE_KEYWORDS = {
        "ai", "exam", "skills", "coaching", "unlimited", "hints", "pro",
        "starter", "enterprise", "basic", "free", "trial", "discount",
        "affordable", "premium", "advanced", "beginner", "intermediate",
        "certification", "placement", "job", "career", "learning",
        "course", "module", "lesson", "quiz", "test", "assessment"
    }

    async def crawl(self, source_id: str, url: str,
                    headline_selector: Optional[str] = None,
                    price_selector: Optional[str] = None,
                    feature_selector: Optional[str] = None,
                    keyword_extraction: bool = True,
                    allow_local: bool = False,
                    allow_browser: bool = True) -> CrawlResult:
        """
        Crawl a competitor website and extract intelligence.

        Strategy:
            1. Fast path: fetch raw HTML via aiohttp and extract.
            2. If the static extraction is empty (no headline AND no pricing AND
               no features) and allow_browser is True, retry using Playwright to
               render JavaScript-injected content, then extract from the rendered
               DOM.

        Args:
            source_id: Unique identifier for this competitor
            url: Website URL to crawl
            headline_selector: CSS selector for headline (optional, uses default if None)
            price_selector: CSS selector for pricing plans (optional, uses default if None)
            feature_selector: CSS selector for features (optional, uses default if None)
            keyword_extraction: Whether to extract keywords from text (default True)
            allow_local: When True, permit loopback/private URLs for local
                development and end-to-end testing (never enable in production).
            allow_browser: When True, fall back to Playwright rendering if static
                extraction finds no meaningful content.

        Returns:
            CrawlResult with extracted data
        """
        # SSRF-safe URL validation: reject loopback/private/link-local targets
        # before any outbound HTTP request is made.
        try:
            safe_url = validate_crawl_url(url, allow_local=allow_local)
        except URLValidationError as exc:
            return CrawlResult(
                source_id=source_id,
                url=url,
                headline="",
                pricing=[],
                features=[],
                keywords=[],
                raw_html="",
                success=False,
                error=f"URL rejected: {exc}",
                attempts=0,
            )

        last_error: Optional[str] = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    async with session.get(safe_url, headers=headers) as resp:
                        # SSRF Redirect Check: Ensure that every redirect hop landed on a safe public URL.
                        for redirect_resp in getattr(resp, "history", ()):
                            try:
                                validate_crawl_url(str(redirect_resp.url), allow_local=allow_local)
                            except URLValidationError as exc:
                                return CrawlResult(
                                    source_id=source_id,
                                    url=safe_url,
                                    headline="",
                                    pricing=[],
                                    features=[],
                                    keywords=[],
                                    raw_html="",
                                    success=False,
                                    error=f"Unsafe redirect blocked: {exc}",
                                    attempts=attempt,
                                )
                        # Also validate the final URL landed upon
                        if hasattr(resp, "url"):
                            try:
                                validate_crawl_url(str(resp.url), allow_local=allow_local)
                            except URLValidationError as exc:
                                return CrawlResult(
                                    source_id=source_id,
                                    url=safe_url,
                                    headline="",
                                    pricing=[],
                                    features=[],
                                    keywords=[],
                                    raw_html="",
                                    success=False,
                                    error=f"Unsafe redirect blocked: {exc}",
                                    attempts=attempt,
                                )

                        # Retry on transient server-side statuses.
                        if resp.status in _RETRYABLE_STATUS and attempt < MAX_ATTEMPTS:
                            last_error = f"HTTP {resp.status} (retrying)"
                            await asyncio.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                            continue

                        if resp.status != 200:
                            return CrawlResult(
                                source_id=source_id,
                                url=safe_url,
                                headline="",
                                pricing=[],
                                features=[],
                                keywords=[],
                                raw_html="",
                                success=False,
                                error=f"HTTP {resp.status}",
                                attempts=attempt,
                            )

                        html = await resp.text()
                        soup = BeautifulSoup(html, 'html.parser')

                        # Extract all components
                        headline = self._extract_headline(soup, headline_selector)
                        pricing = self._extract_pricing(soup, price_selector)
                        features = self._extract_features(soup, feature_selector)
                        keywords = self._extract_keywords(soup, headline, keyword_extraction)

                        # If static extraction is empty and browser is allowed,
                        # fall back to Playwright rendering for JS-heavy sites.
                        is_empty = not headline and not pricing and not features
                        if is_empty and allow_browser:
                            browser_result = await self._render_with_browser(
                                source_id, safe_url, allow_local,
                                headline_selector, price_selector,
                                feature_selector, keyword_extraction,
                            )
                            if browser_result is not None:
                                browser_result.browser_rendered = True
                                return browser_result

                        return CrawlResult(
                            source_id=source_id,
                            url=safe_url,
                            headline=headline,
                            pricing=pricing,
                            features=features,
                            keywords=keywords,
                            raw_html=html[:10000],  # Truncate for storage
                            success=True,
                            attempts=attempt,
                        )
            except (asyncio.TimeoutError, aiohttp.ClientError) as exc:
                last_error = str(exc)
                if attempt < MAX_ATTEMPTS:
                    await asyncio.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)))
                    continue
            except Exception as e:
                # Non-retryable error: fail immediately without burning retries.
                return CrawlResult(
                    source_id=source_id,
                    url=safe_url,
                    headline="",
                    pricing=[],
                    features=[],
                    keywords=[],
                    raw_html="",
                    success=False,
                    error=str(e),
                    attempts=attempt,
                )

        return CrawlResult(
            source_id=source_id,
            url=safe_url,
            headline="",
            pricing=[],
            features=[],
            keywords=[],
            raw_html="",
            success=False,
            error=last_error or f"Failed after {MAX_ATTEMPTS} attempts",
            attempts=MAX_ATTEMPTS,
        )
    
    def _extract_headline(self, soup: BeautifulSoup, selector: Optional[str] = None) -> str:
        """Extract primary headline/messaging."""
        if selector:
            selectors = [selector]
        else:
            selectors = self.HEADLINE_SELECTORS
        for sel in selectors:
            elem = soup.select_one(sel)
            if elem:
                return elem.get_text(strip=True)
        return ""
    
    def _extract_pricing(self, soup: BeautifulSoup, selector: Optional[str] = None) -> List[Dict[str, Any]]:
        """Extract pricing tiers and plans."""
        plans = []
        seen = set()

        if selector:
            selectors = [selector]
        else:
            selectors = self.PRICE_SELECTORS

        for sel in selectors:
            elements = soup.select(sel)
            for elem in elements:
                plan = self._parse_plan_element(elem)
                if plan and plan.get("price"):
                    key = (plan["name"].strip().lower(), plan["price"].strip())
                    if key not in seen:
                        seen.add(key)
                        plans.append(plan)
            # If default selectors matched plans on a higher-level container,
            # break to prevent nested selectors (like [class*='price']) from
            # extracting fragment duplicate plans.
            if plans and not selector:
                break

        # Also search for price patterns in text
        if not plans:
            plans = self._extract_prices_from_text(soup)

        return plans

    def _parse_plan_element(self, elem: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Parse a single pricing plan element."""
        try:
            # Get plan name
            name = ""
            name_elem = elem.select_one("h2, h3, .plan-name, [class*='name'], .title")
            if name_elem:
                name = name_elem.get_text(strip=True)

            # Get price
            price = ""
            price_elem = elem.select_one(".price, [class*='price'], .amount, .cost")
            if price_elem:
                price = price_elem.get_text(strip=True)
            else:
                # Try to find price in text
                text = elem.get_text()
                price_match = re.search(r'[₹$£€]\s*\d+(?:,\d{3})*(?:\.\d{2})?', text)
                if price_match:
                    price = price_match.group(0)

            # Get features - prefer li items, otherwise leaf feature elements
            features = []
            feature_elems = elem.select("li") or elem.select(".feature")
            for f in feature_elems:
                feat_text = f.get_text(strip=True)
                if feat_text and len(feat_text) > 3:
                    features.append(feat_text)

            if name or price:
                return {
                    "name": name or "Plan",
                    "price": price,
                    "features": features[:5]  # Limit features
                }
        except Exception:
            pass
        return None
    
    def _extract_prices_from_text(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Fallback: extract prices from page text."""
        text = soup.get_text()
        plans = []
        
        # Look for price patterns
        price_pattern = r'([₹$£€])\s*(\d+(?:,\d{3})*(?:\.\d{2})?)\s*(?:per|/|\s)?\s*(month|year|annum|mo|yr)?'
        matches = re.finditer(price_pattern, text, re.IGNORECASE)
        
        for i, match in enumerate(matches):
            currency = match.group(1)
            amount = match.group(2)
            period = match.group(3) or "month"
            
            plans.append({
                "name": f"Tier {i+1}",
                "price": f"{currency}{amount}/{period}",
                "features": []
            })
        
        return plans
    
    def _extract_features(self, soup: BeautifulSoup, selector: Optional[str] = None) -> List[str]:
        """Extract feature list from page."""
        features = []
        
        # Look for feature lists
        if selector:
            selectors = [selector]
        else:
            selectors = [
                ".features li", ".feature-list li", "[class*='feature'] li",
                ".benefits li", ".benefit", "[class*='benefit']"
            ]
        
        for sel in selectors:
            elems = soup.select(sel)
            for elem in elems:
                text = elem.get_text(strip=True)
                if text and len(text) > 5:
                    features.append(text)
        
        return list(set(features))[:10]  # Deduplicate and limit
    
    def _extract_keywords(self, soup: BeautifulSoup, headline: str, keyword_extraction: bool = True) -> List[str]:
        """Extract marketing keywords from content."""
        if not keyword_extraction:
            return []
        text = soup.get_text().lower()
        if headline:
            text += " " + headline.lower()
        
        found = set()
        for keyword in self.FEATURE_KEYWORDS:
            if keyword in text:
                found.add(keyword)
        
        return sorted(list(found))

    # ----------------------------------------------------------------- #
    #  Playwright browser fallback                                       #
    # ----------------------------------------------------------------- #
    async def _render_with_browser(
        self,
        source_id: str,
        url: str,
        allow_local: bool,
        headline_selector: Optional[str] = None,
        price_selector: Optional[str] = None,
        feature_selector: Optional[str] = None,
        keyword_extraction: bool = True,
    ) -> Optional[CrawlResult]:
        """
        Render a JS-heavy page using Playwright and extract content from the
        live DOM. Returns None if the browser cannot be launched or the page
        fails to load, so the caller can decide how to handle it.

        All SSRF safety checks are re-applied: the URL is validated again and
        every redirect is vetted against the public-IP allowlist.
        """
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            logger.warning("Playwright not installed; browser fallback unavailable")
            return None

        # Re-validate the URL (SSRF safety) before launching the browser.
        try:
            safe_url = validate_crawl_url(url, allow_local=allow_local)
        except URLValidationError as exc:
            return CrawlResult(
                source_id=source_id,
                url=url,
                headline="",
                pricing=[],
                features=[],
                keywords=[],
                raw_html="",
                success=False,
                error=f"Browser URL rejected: {exc}",
                attempts=0,
            )

        browser = None
        context = None
        page = None
        try:
            async with async_playwright() as p:
                # Launch a fresh browser instance.
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context()
                page = await context.new_page()

                # SSRF guard on all browser-initiated subrequests and redirects
                if not allow_local:
                    async def _route_ssrf_filter(route, request):
                        req_url = request.url
                        # Data URIs and blob URIs are safe internal browser objects
                        if req_url.startswith(("data:", "blob:", "about:")):
                            await route.continue_()
                            return
                        try:
                            validate_crawl_url(req_url, allow_local=False)
                            await route.continue_()
                        except URLValidationError:
                            logger.warning(f"Browser SSRF block: intercepted unsafe request to {req_url}")
                            await route.abort()

                    await page.route("**/*", _route_ssrf_filter)

                # Navigate with a bounded timeout.
                await page.goto(
                    safe_url,
                    wait_until="domcontentloaded",
                    timeout=BROWSER_NAVIGATION_TIMEOUT,
                )

                # Wait a short grace period for JS to populate the DOM.
                try:
                    await page.wait_for_load_state("networkidle", timeout=2000)
                except Exception:
                    # networkidle can time out on long-polling sites; that's OK.
                    pass
                # A small additional sleep to allow short setTimeout callbacks to execute.
                await asyncio.sleep(0.3)

                # Grab the rendered HTML.
                html = await page.content()
                soup = BeautifulSoup(html, 'html.parser')

                headline = self._extract_headline(soup, headline_selector)
                pricing = self._extract_pricing(soup, price_selector)
                features = self._extract_features(soup, feature_selector)
                keywords = self._extract_keywords(soup, headline, keyword_extraction)

                return CrawlResult(
                    source_id=source_id,
                    url=safe_url,
                    headline=headline,
                    pricing=pricing,
                    features=features,
                    keywords=keywords,
                    raw_html=html[:10000],
                    success=True,
                    attempts=1,
                )
        except asyncio.TimeoutError:
            return CrawlResult(
                source_id=source_id,
                url=safe_url,
                headline="",
                pricing=[],
                features=[],
                keywords=[],
                raw_html="",
                success=False,
                error="Browser navigation timed out",
                attempts=1,
            )
        except Exception as exc:
            return CrawlResult(
                source_id=source_id,
                url=safe_url,
                headline="",
                pricing=[],
                features=[],
                keywords=[],
                raw_html="",
                success=False,
                error=f"Browser rendering failed: {exc}",
                attempts=1,
            )
        finally:
            # Ensure resources are released on all paths.
            try:
                if page is not None:
                    await page.close()
            except Exception:
                pass
            try:
                if context is not None:
                    await context.close()
            except Exception:
                pass
            try:
                if browser is not None:
                    await browser.close()
            except Exception:
                pass


# Global crawler instance
crawler = CompetitorCrawler()


async def crawl_competitor(competitor: Dict[str, Any]) -> CrawlResult:
    """Convenience function to crawl a single competitor."""
    from app.config import settings
    return await crawler.crawl(
        source_id=competitor["source_id"],
        url=competitor["url"],
        headline_selector=competitor.get("headline_selector"),
        price_selector=competitor.get("price_selector"),
        feature_selector=competitor.get("feature_selector"),
        keyword_extraction=competitor.get("keyword_extraction", True),
        allow_local=settings.ALLOW_LOCAL_CRAWLS
    )


async def crawl_multiple(competitors: List[Dict[str, Any]]) -> List[CrawlResult]:
    """
    Crawl multiple competitors concurrently.

    Args:
        competitors: List of dicts with competitor data

    Returns:
        List of CrawlResults
    """
    tasks = [
        crawl_competitor(c)
        for c in competitors
    ]
    return await asyncio.gather(*tasks)

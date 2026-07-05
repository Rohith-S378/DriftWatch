"""
Active web crawler for competitor intelligence.
Fetches competitor websites, extracts pricing, messaging, and features.
"""
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re


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
                    keyword_extraction: bool = True) -> CrawlResult:
        """
        Crawl a competitor website and extract intelligence.

        Args:
            source_id: Unique identifier for this competitor
            url: Website URL to crawl
            headline_selector: CSS selector for headline (optional, uses default if None)
            price_selector: CSS selector for pricing plans (optional, uses default if None)
            feature_selector: CSS selector for features (optional, uses default if None)
            keyword_extraction: Whether to extract keywords from text (default True)

        Returns:
            CrawlResult with extracted data
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                async with session.get(url, headers=headers) as resp:
                    if resp.status != 200:
                        return CrawlResult(
                            source_id=source_id,
                            url=url,
                            headline="",
                            pricing=[],
                            features=[],
                            keywords=[],
                            raw_html="",
                            success=False,
                            error=f"HTTP {resp.status}"
                        )

                    html = await resp.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Extract all components
                    headline = self._extract_headline(soup, headline_selector)
                    pricing = self._extract_pricing(soup, price_selector)
                    features = self._extract_features(soup, feature_selector)
                    keywords = self._extract_keywords(soup, headline, keyword_extraction)

                    return CrawlResult(
                        source_id=source_id,
                        url=url,
                        headline=headline,
                        pricing=pricing,
                        features=features,
                        keywords=keywords,
                        raw_html=html[:10000],  # Truncate for storage
                        success=True
                    )

        except Exception as e:
            return CrawlResult(
                source_id=source_id,
                url=url,
                headline="",
                pricing=[],
                features=[],
                keywords=[],
                raw_html="",
                success=False,
                error=str(e)
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
        
        if selector:
            selectors = [selector]
        else:
            selectors = self.PRICE_SELECTORS

        for sel in selectors:
            elements = soup.select(sel)
            for elem in elements:
                plan = self._parse_plan_element(elem)
                if plan:
                    plans.append(plan)
        
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
            
            # Get features
            features = []
            feature_elems = elem.select("li, .feature, [class*='feature']")
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


# Global crawler instance
crawler = CompetitorCrawler()


async def crawl_competitor(competitor: Dict[str, Any]) -> CrawlResult:
    """Convenience function to crawl a single competitor."""
    return await crawler.crawl(
        source_id=competitor["source_id"],
        url=competitor["url"],
        headline_selector=competitor.get("headline_selector"),
        price_selector=competitor.get("price_selector"),
        feature_selector=competitor.get("feature_selector"),
        keyword_extraction=competitor.get("keyword_extraction", True)
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

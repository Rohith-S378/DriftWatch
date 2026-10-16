"""
Search Provider Interfaces and Adapters for Competitor Discovery.
Includes:
- Abstract SearchProviderBase
- TavilySearchProvider (API key configured via TAVILY_API_KEY)
- SerpApiSearchProvider (API key configured via SERPAPI_API_KEY)
- MockSearchProvider (for deterministic offline testing and local verification)
- Factory function get_search_provider()
"""
from __future__ import annotations

from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Dict, List, Optional, Any
import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class SearchResultItem:
    def __init__(self, title: str, url: str, snippet: str, raw_data: Optional[Dict[str, Any]] = None):
        self.title = title
        self.url = url
        self.snippet = snippet
        self.raw_data = raw_data or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "raw_data": self.raw_data,
        }


class SearchProviderBase(ABC):
    """Abstract base class for search provider adapters."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has the required configuration/credentials."""
        pass

    @abstractmethod
    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        """Execute a search query and return normalized search items."""
        pass


class TavilySearchProvider(SearchProviderBase):
    """Adapter for the Tavily Search API."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.TAVILY_API_KEY

    @property
    def name(self) -> str:
        return "tavily"

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        if not self.is_configured():
            raise RuntimeError("Tavily API key is not configured. Set TAVILY_API_KEY in environment.")

        endpoint = "https://api.tavily.com/search"
        payload = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "basic",
            "include_answer": False,
            "max_results": max_results,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(endpoint, json=payload)
            if resp.status_code != 200:
                raise RuntimeError(f"Tavily search failed: HTTP {resp.status_code} - {resp.text}")
            data = resp.json()

        results = []
        for r in data.get("results", []):
            results.append(
                SearchResultItem(
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    snippet=r.get("content", ""),
                    raw_data=r,
                )
            )
        return results


class SerpApiSearchProvider(SearchProviderBase):
    """Adapter for SerpAPI Google Search."""

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or settings.SERPAPI_API_KEY

    @property
    def name(self) -> str:
        return "serpapi"

    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.strip())

    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        if not self.is_configured():
            raise RuntimeError("SerpAPI key is not configured. Set SERPAPI_API_KEY in environment.")

        endpoint = "https://serpapi.com/search"
        params = {
            "api_key": self._api_key,
            "q": query,
            "engine": "google",
            "num": max_results,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(endpoint, params=params)
            if resp.status_code != 200:
                raise RuntimeError(f"SerpAPI search failed: HTTP {resp.status_code} - {resp.text}")
            data = resp.json()

        results = []
        for r in data.get("organic_results", []):
            results.append(
                SearchResultItem(
                    title=r.get("title", ""),
                    url=r.get("link", ""),
                    snippet=r.get("snippet", ""),
                    raw_data=r,
                )
            )
        return results


class MockSearchProvider(SearchProviderBase):
    """
    Mock search provider for deterministic testing and local verification.
    Supplies canned candidates when configured query terms match.
    """

    def __init__(self, custom_results: Optional[Dict[str, List[Dict[str, str]]]] = None):
        self._custom_results = custom_results or {
            "edtech": [
                {
                    "title": "Coursera Online Learning & Degrees",
                    "url": "https://www.coursera.org",
                    "snippet": "Learn skills and certifications online with top university and industry courses.",
                },
                {
                    "title": "Udemy Online Courses & Certifications",
                    "url": "https://www.udemy.com",
                    "snippet": "Choose from over 210,000 online video courses with new additions published every month.",
                },
                {
                    "title": "Scaler Academy Tech Upskilling",
                    "url": "https://www.scaler.com",
                    "snippet": "Accelerate your tech career with mentorship, career placement, and live classes.",
                },
            ],
            "default": [
                {
                    "title": "Cloudflare Global Cloud Platform",
                    "url": "https://www.cloudflare.com",
                    "snippet": "Cloud security, performance, and reliability company helping build a better Internet.",
                },
                {
                    "title": "Fastly Edge Cloud Platform",
                    "url": "https://www.fastly.com",
                    "snippet": "Programmable edge cloud platform for real-time digital experiences.",
                },
            ]
        }

    @property
    def name(self) -> str:
        return "mock"

    def is_configured(self) -> bool:
        return True

    async def search(self, query: str, max_results: int = 5) -> List[SearchResultItem]:
        q_lower = query.lower()
        items_data = []
        if any(term in q_lower for term in ["edtech", "learning", "course", "exam", "coaching", "quiz", "certification"]):
            items_data = self._custom_results.get("edtech", [])
        else:
            items_data = self._custom_results.get("default", [])

        results = [
            SearchResultItem(
                title=item["title"],
                url=item["url"],
                snippet=item["snippet"],
                raw_data=item,
            )
            for item in items_data[:max_results]
        ]
        return results


def get_search_provider(preferred_provider: Optional[str] = None) -> SearchProviderBase:
    """
    Factory to retrieve the appropriate configured search provider.
    Priority:
    1. If explicitly requested ('tavily', 'serpapi', 'mock')
    2. Tavily if TAVILY_API_KEY is configured
    3. SerpAPI if SERPAPI_API_KEY is configured
    4. Mock if DISCOVERY_SEARCH_PROVIDER is 'mock'
    """
    prov_name = (preferred_provider or settings.DISCOVERY_SEARCH_PROVIDER).lower()

    if prov_name == "tavily":
        return TavilySearchProvider()
    elif prov_name == "serpapi":
        return SerpApiSearchProvider()
    elif prov_name == "mock":
        return MockSearchProvider()

    # 'auto' mode: check available API keys
    if settings.TAVILY_API_KEY:
        return TavilySearchProvider()
    if settings.SERPAPI_API_KEY:
        return SerpApiSearchProvider()

    # Fallback to mock provider with a clear logged note
    logger.info("No external search API keys found (TAVILY_API_KEY / SERPAPI_API_KEY). Using MockSearchProvider.")
    return MockSearchProvider()

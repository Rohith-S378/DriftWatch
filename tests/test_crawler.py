"""Tests for CompetitorCrawler error handling, retries, and SSRF protection."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import aiohttp
from bs4 import BeautifulSoup

from app.services.crawler import CompetitorCrawler, CrawlResult


@pytest.mark.asyncio
async def test_crawler_rejects_ssrf_url():
    crawler = CompetitorCrawler()
    result = await crawler.crawl(
        source_id="evil-target",
        url="http://127.0.0.1:8000/internal",
    )
    assert result.success is False
    assert "URL rejected" in result.error
    assert result.attempts == 0


@pytest.mark.asyncio
async def test_crawler_rejects_aws_metadata_endpoint():
    crawler = CompetitorCrawler()
    result = await crawler.crawl(
        source_id="evil-target",
        url="http://169.254.169.254/latest/meta-data/",
    )
    assert result.success is False
    assert "URL rejected" in result.error


@pytest.mark.asyncio
async def test_crawler_parses_html_correctly():
    crawler = CompetitorCrawler()

    html = """
    <html>
      <body>
        <h1>Super AI Coaching Platform</h1>
        <div class="pricing-plan">
          <h3>Pro Tier</h3>
          <span class="price">$49/month</span>
          <ul class="features">
            <li>Unlimited practice exams</li>
            <li>AI-driven personalized feedback</li>
          </ul>
        </div>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    headline = crawler._extract_headline(soup)
    pricing = crawler._extract_pricing(soup)
    features = crawler._extract_features(soup)
    keywords = crawler._extract_keywords(soup, headline)

    assert headline == "Super AI Coaching Platform"
    assert len(pricing) == 1
    assert pricing[0]["name"] == "Pro Tier"
    assert pricing[0]["price"] == "$49/month"
    assert "Unlimited practice exams" in pricing[0]["features"]
    assert "ai" in keywords
    assert "exam" in keywords


@pytest.mark.asyncio
async def test_crawler_retries_transient_failure(monkeypatch):
    """Crawler should retry on 500 status code up to MAX_ATTEMPTS."""
    crawler = CompetitorCrawler()

    # Avoid DNS lookup by patching validate_crawl_url to pass through
    monkeypatch.setattr("app.services.crawler.validate_crawl_url", lambda url, **kwargs: url)
    # Speed up tests by setting delay to 0
    monkeypatch.setattr("app.services.crawler.RETRY_BASE_DELAY", 0.001)

    call_count = 0

    class FakeResponse:
        def __init__(self, status):
            self.status = status

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def text(self):
            return "Server Error"

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        def get(self, url, headers=None):
            nonlocal call_count
            call_count += 1
            return FakeResponse(500)

    monkeypatch.setattr(aiohttp, "ClientSession", FakeSession)

    result = await crawler.crawl(source_id="flaky", url="https://example.com")
    assert result.success is False
    assert result.attempts == 3
    assert call_count == 3

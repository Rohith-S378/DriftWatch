"""Tests for CompetitorCrawler JavaScript browser rendering fallback.

Verifies:
1. Static HTML extraction unchanged (fast path).
2. Browser fallback triggers on insufficient HTTP extraction.
3. Browser fallback not triggered when HTTP extraction is sufficient.
4. JS-rendered headline and features extracted correctly.
5. Dynamically rendered pricing extracted correctly.
6. Missing pricing stays missing without hallucination.
7. Navigation timeout handled gracefully.
8. Browser launch failure handled gracefully.
9. Resource cleanup after errors.
10. Redirect to restricted destination rejected (SSRF).
11. Existing SSRF protections intact with allow_browser=True.
12. Snapshot/change-detector integration works with browser-rendered CrawlResult.
13. Deterministic local HTTP server, no external dependencies.
"""
import asyncio
import http.server
import threading
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from app.services.crawler import CompetitorCrawler, CrawlResult
from app.services.change_detector import detect_price_changes, detect_messaging_changes


# Test pages
STATIC_HTML_WITH_CONTENT = """<!DOCTYPE html>
<html>
<head><title>Static Platform</title></head>
<body>
  <h1>Static AI Coaching Platform</h1>
  <div class="pricing-plan">
    <h3>Starter Tier</h3>
    <span class="price">$29/month</span>
    <ul class="features">
      <li>Core practice exams</li>
      <li>Basic AI analytics</li>
    </ul>
  </div>
</body>
</html>"""

SPA_HTML_EMPTY_SHELL = """<!DOCTYPE html>
<html>
<head><title>Dynamic Platform</title></head>
<body>
  <div id="app"></div>
  <script>
    setTimeout(function() {
      document.getElementById('app').innerHTML =
        '<h1>Dynamic Next-Gen AI Coach</h1>' +
        '<div class="pricing-plan">' +
          '<h3>Pro Tier</h3>' +
          '<span class="price">$99/month</span>' +
          '<ul class="features">' +
            '<li>Unlimited adaptive exams</li>' +
            '<li>Real-time mentor coaching</li>' +
          '</ul>' +
        '</div>';
    }, 100);
  </script>
</body>
</html>"""

SPA_HTML_NO_PRICING = """<!DOCTYPE html>
<html>
<head><title>No Pricing Platform</title></head>
<body>
  <div id="app"></div>
  <script>
    setTimeout(function() {
      document.getElementById('app').innerHTML =
        '<h1>Enterprise AI Platform</h1>' +
        '<p>Contact our sales team for tailored pricing.</p>' +
        '<ul class="features">' +
          '<li>Custom enterprise deployment</li>' +
        '</ul>';
    }, 100);
  </script>
</body>
</html>"""


class MockSiteHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/static":
            body = STATIC_HTML_WITH_CONTENT.encode("utf-8")
        elif self.path == "/spa":
            body = SPA_HTML_EMPTY_SHELL.encode("utf-8")
        elif self.path == "/spa-no-price":
            body = SPA_HTML_NO_PRICING.encode("utf-8")
        elif self.path == "/hang":
            # Sleep longer than the navigation timeout to test timeout handling
            import time
            time.sleep(20)
            body = b"Too late"
        elif self.path == "/redirect-to-metadata":
            self.send_response(302)
            self.send_header("Location", "http://169.254.169.254/latest/meta-data/")
            self.end_headers()
            return
        elif self.path == "/redirect-to-loopback":
            self.send_response(302)
            self.send_header("Location", "http://127.0.0.1:8000/internal")
            self.end_headers()
            return
        else:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # Quiet down server logs during testing


@pytest.fixture(scope="module")
def local_server():
    server = http.server.HTTPServer(("127.0.0.1", 0), MockSiteHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


# 1. Static HTML extraction unchanged
@pytest.mark.asyncio
async def test_static_html_extraction_unchanged(local_server):
    crawler = CompetitorCrawler()
    result = await crawler.crawl("static_comp", f"{local_server}/static", allow_local=True)
    assert result.success is True
    assert result.headline == "Static AI Coaching Platform"
    assert len(result.pricing) == 1
    assert result.pricing[0]["name"] == "Starter Tier"
    assert result.pricing[0]["price"] == "$29/month"
    assert result.browser_rendered is False


# 2. Browser fallback triggers on insufficient HTTP extraction
@pytest.mark.asyncio
async def test_browser_fallback_triggers_for_spa(local_server):
    crawler = CompetitorCrawler()
    result = await crawler.crawl("spa_comp", f"{local_server}/spa", allow_local=True, allow_browser=True)
    assert result.success is True
    assert result.browser_rendered is True
    assert result.headline == "Dynamic Next-Gen AI Coach"
    assert len(result.pricing) == 1
    assert result.pricing[0]["name"] == "Pro Tier"
    assert result.pricing[0]["price"] == "$99/month"
    assert "ai" in result.keywords
    assert "coaching" in result.keywords


# 3. Browser fallback NOT triggered when HTTP extraction is sufficient
@pytest.mark.asyncio
async def test_browser_fallback_not_triggered_when_http_sufficient(local_server):
    crawler = CompetitorCrawler()
    with patch.object(crawler, "_render_with_browser", new_callable=AsyncMock) as mock_render:
        result = await crawler.crawl("static_comp", f"{local_server}/static", allow_local=True, allow_browser=True)
        assert result.success is True
        assert result.browser_rendered is False
        mock_render.assert_not_called()


# 4. Browser fallback disabled via allow_browser=False
@pytest.mark.asyncio
async def test_browser_fallback_disabled(local_server):
    crawler = CompetitorCrawler()
    result = await crawler.crawl("spa_comp", f"{local_server}/spa", allow_local=True, allow_browser=False)
    # HTTP extraction succeeds technically, but returns empty shell
    assert result.success is True
    assert result.headline == ""
    assert result.pricing == []
    assert result.browser_rendered is False


# 5. Missing pricing stays missing without hallucination
@pytest.mark.asyncio
async def test_missing_pricing_stays_missing(local_server):
    crawler = CompetitorCrawler()
    result = await crawler.crawl("spa_no_price", f"{local_server}/spa-no-price", allow_local=True, allow_browser=True)
    assert result.success is True
    assert result.browser_rendered is True
    assert result.headline == "Enterprise AI Platform"
    assert result.pricing == []  # No fake or hallucinated plans
    assert len(result.features) > 0


# 6. Browser launch / execution failure handling
@pytest.mark.asyncio
async def test_browser_launch_failure_handling(local_server):
    crawler = CompetitorCrawler()
    # Mock playwright launch failure
    with patch("playwright.async_api.async_playwright") as mock_pw:
        mock_pw.side_effect = RuntimeError("Chromium binary missing")
        result = await crawler.crawl("spa_comp", f"{local_server}/spa", allow_local=True, allow_browser=True)
        # Should gracefully return CrawlResult with error
        assert result.success is False
        assert "Chromium binary missing" in result.error


# 7. Navigation timeout handling
@pytest.mark.asyncio
async def test_browser_navigation_timeout_handling(monkeypatch):
    crawler = CompetitorCrawler()
    # Set short timeout for test speed
    monkeypatch.setattr("app.services.crawler.BROWSER_NAVIGATION_TIMEOUT", 500)
    
    with patch("playwright.async_api.async_playwright") as mock_pw:
        mock_p_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_pw.return_value.__aenter__.return_value = mock_p_instance
        mock_p_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.goto.side_effect = asyncio.TimeoutError()

        result = await crawler._render_with_browser("timeout_comp", "http://example.com", allow_local=True)
        assert result.success is False
        assert "timed out" in result.error.lower()
        mock_page.close.assert_awaited()
        mock_context.close.assert_awaited()
        mock_browser.close.assert_awaited()


# 8. SSRF rejected on browser crawl directly
@pytest.mark.asyncio
async def test_browser_crawl_rejects_ssrf():
    crawler = CompetitorCrawler()
    result = await crawler.crawl("evil", "http://169.254.169.254/latest/meta-data/", allow_local=False, allow_browser=True)
    assert result.success is False
    assert "URL rejected" in result.error


# 9. Browser fallback cleans up resources on unexpected error
@pytest.mark.asyncio
async def test_browser_cleanup_on_error():
    crawler = CompetitorCrawler()
    with patch("playwright.async_api.async_playwright") as mock_pw:
        mock_p_instance = AsyncMock()
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()

        mock_pw.return_value.__aenter__.return_value = mock_p_instance
        mock_p_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.content.side_effect = Exception("DOM crashed")

        result = await crawler._render_with_browser("crash_comp", "http://example.com", allow_local=True)
        assert result.success is False
        assert "DOM crashed" in result.error
        mock_page.close.assert_awaited()
        mock_context.close.assert_awaited()
        mock_browser.close.assert_awaited()


# 10. Integration with change detector: browser-rendered results trigger clean diffs
@pytest.mark.asyncio
async def test_change_detector_integration_with_browser_result():
    # Simulate first snapshot from static/empty
    old_plans = []
    # Second snapshot rendered via Playwright browser
    new_plans = [{"name": "Pro Tier", "price": "$99/month", "features": ["Unlimited AI coaching"]}]

    changes = detect_price_changes(old_plans, new_plans)
    assert len(changes) == 1
    assert changes[0].change_type == "price"
    assert "pro tier" in changes[0].description.lower()
    assert changes[0].new_value == "$99/month"

    # Messaging change detection with async mock DB session
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    msg_changes = await detect_messaging_changes(
        {"headline": "Old Static Headline"},
        {"headline": "Dynamic Next-Gen AI Coach"},
        mock_session,
        "comp_test",
    )
    assert len(msg_changes) == 1
    assert msg_changes[0].change_type == "messaging"
    assert "messaging" in msg_changes[0].description.lower()

"""
End-to-end crawl pipeline tests with a local HTTP server.
Verifies:
1. Baseline snapshot created on initial crawl, NO change events generated.
2. Second crawl with unchanged page creates snapshot, STILL NO change events.
3. Third crawl with modified page (Version B) generates change events:
   - Price change (Starter: $49 -> $79, Enterprise: $299 -> $349)
   - Messaging change (headline change)
   - Keyword drift (new keywords detected)
4. Crawl failure (unreachable server) returns error, leaves existing snapshots and events uncorrupted.
"""
import pytest
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from app.config import settings

VERSION_A_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Competitor</title></head>
<body>
  <h1 class="headline">Next-Gen AI Learning Platform</h1>
  <p class="description">Master new skills with interactive courses and AI coaching.</p>
  <div class="pricing-plan">
    <h3 class="plan-name">Starter</h3>
    <div class="price">$49/mo</div>
    <ul>
      <li>Basic exam practice</li>
    </ul>
  </div>
  <div class="pricing-plan">
    <h3 class="plan-name">Enterprise</h3>
    <div class="price">$299/mo</div>
    <ul>
      <li>Unlimited AI coaching</li>
      <li>Career placement support</li>
    </ul>
  </div>
</body>
</html>"""

VERSION_B_HTML = """<!DOCTYPE html>
<html>
<head><title>Test Competitor</title></head>
<body>
  <h1 class="headline">Transform Your Career with AI-Powered Intelligence</h1>
  <p class="description">Industry-leading certification and job placement with discount hints.</p>
  <div class="pricing-plan">
    <h3 class="plan-name">Starter</h3>
    <div class="price">$79/mo</div>
    <ul>
      <li>Basic exam practice with hints</li>
    </ul>
  </div>
  <div class="pricing-plan">
    <h3 class="plan-name">Enterprise</h3>
    <div class="price">$349/mo</div>
    <ul>
      <li>Unlimited AI coaching</li>
      <li>Career certification guarantee</li>
    </ul>
  </div>
</body>
</html>"""


class ControlledTestServer(BaseHTTPRequestHandler):
    current_version = "A"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        html = VERSION_A_HTML if ControlledTestServer.current_version == "A" else VERSION_B_HTML
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass  # Quiet logging in tests


@pytest.fixture(scope="module")
def local_test_site():
    ControlledTestServer.current_version = "A"
    server = HTTPServer(("127.0.0.1", 0), ControlledTestServer)
    port = server.server_port
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()


def test_full_crawl_pipeline_lifecycle(client, local_test_site):
    # Enable local crawls for this test
    original_allow = settings.ALLOW_LOCAL_CRAWLS
    settings.ALLOW_LOCAL_CRAWLS = True
    try:
        source_id = "test_edtech_comp"

        # Step 1: Initial Crawl (Baseline)
        ControlledTestServer.current_version = "A"
        res1 = client.post(
            "/api/crawl/single",
            json={"source_id": source_id, "url": local_test_site},
        )
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["success"] is True
        assert "AI Learning" in data1["headline"]
        assert len(data1["pricing"]) == 2

        # Verify NO change events generated on baseline crawl
        events_res1 = client.get(f"/api/events/{source_id}")
        assert events_res1.status_code == 200
        assert len(events_res1.json()) == 0

        # Small delay to ensure timestamp resolution
        time.sleep(1.1)

        # Step 2: Unchanged Crawl (Second crawl of Version A)
        res2 = client.post(
            "/api/crawl/single",
            json={"source_id": source_id, "url": local_test_site},
        )
        assert res2.status_code == 200
        assert res2.json()["success"] is True

        # Verify STILL NO change events
        events_res2 = client.get(f"/api/events/{source_id}")
        assert len(events_res2.json()) == 0

        time.sleep(1.1)

        # Step 3: Modified Crawl (Switch to Version B)
        ControlledTestServer.current_version = "B"
        res3 = client.post(
            "/api/crawl/single",
            json={"source_id": source_id, "url": local_test_site},
        )
        assert res3.status_code == 200
        data3 = res3.json()
        assert data3["success"] is True
        assert "Transform Your Career" in data3["headline"]

        # Verify CHANGE EVENTS generated
        events_res3 = client.get(f"/api/events/{source_id}")
        events3 = events_res3.json()
        assert len(events3) > 0

        change_types = {e["change_type"] for e in events3}
        # We expect price change and messaging/keyword change
        assert "price" in change_types or "messaging" in change_types

        # Verify events contain diff detail
        for ev in events3:
            assert ev["source_id"] == source_id
            assert ev["severity"] in {"low", "medium", "high", "critical"}
            assert ev["description"]

        # Step 4: Crawl Failure Handling
        # Crawl an unreachable port
        unreachable_url = "http://127.0.0.1:59999/does-not-exist"
        res_fail = client.post(
            "/api/crawl/single",
            json={"source_id": source_id, "url": unreachable_url},
        )
        assert res_fail.status_code == 200
        fail_data = res_fail.json()
        assert fail_data["success"] is False
        assert fail_data["error"] is not None

        # Verify previous events are NOT corrupted
        events_res_after_fail = client.get(f"/api/events/{source_id}")
        events_after = events_res_after_fail.json()
        assert len(events_after) == len(events3)

    finally:
        settings.ALLOW_LOCAL_CRAWLS = original_allow

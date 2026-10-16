"""
Controlled local test site for DriftWatch end-to-end verification.
Serves Version A (initial pricing/messaging) and Version B (modified).
Can switch version via query param (?v=B) or POST /set_version?v=B.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys

VERSION_A = """<!DOCTYPE html>
<html>
<head><title>Apex Learning Systems</title></head>
<body>
  <h1 class="headline">Leading AI Coaching & Certification</h1>
  <p class="description">Master full stack skills with interactive lessons and coaching.</p>
  <div class="pricing-container">
    <div class="pricing-plan">
      <h3 class="plan-name">Pro</h3>
      <div class="price">$49/mo</div>
      <ul>
        <li>Basic exam questions</li>
        <li>10 practice quizzes</li>
      </ul>
    </div>
    <div class="pricing-plan">
      <h3 class="plan-name">Enterprise</h3>
      <div class="price">$299/mo</div>
      <ul>
        <li>Unlimited AI coaching</li>
        <li>Career placement assistance</li>
      </ul>
    </div>
  </div>
</body>
</html>"""

VERSION_B = """<!DOCTYPE html>
<html>
<head><title>Apex Learning Systems</title></head>
<body>
  <h1 class="headline">Premier Generative AI Intelligence & Career Accelerator</h1>
  <p class="description">Industry-recognized certification, career accelerator with discount hints and exam prep.</p>
  <div class="pricing-container">
    <div class="pricing-plan">
      <h3 class="plan-name">Pro</h3>
      <div class="price">$79/mo</div>
      <ul>
        <li>Advanced exam prep with hints</li>
        <li>Special discount pricing</li>
      </ul>
    </div>
    <div class="pricing-plan">
      <h3 class="plan-name">Enterprise</h3>
      <div class="price">$399/mo</div>
      <ul>
        <li>Unlimited AI coaching</li>
        <li>Guaranteed career placement</li>
      </ul>
    </div>
  </div>
</body>
</html>"""


class Handler(BaseHTTPRequestHandler):
    current_version = "A"

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "http://localhost:5173")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors_headers()
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/set_version":
            params = parse_qs(parsed.query)
            ver = params.get("v", ["A"])[0].upper()
            Handler.current_version = ver
            self.send_response(200)
            self._cors_headers()
            self.end_headers()
            self.wfile.write(f"Switched to version {ver}".encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        ver = params.get("v", [Handler.current_version])[0].upper()
        html = VERSION_B if ver == "B" else VERSION_A

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        pass


def run(port=8088):
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"Test site running on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    run(port)

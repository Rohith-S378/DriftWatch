# demo_backup.py
# Run this if scraper or API fails during presentation
# It starts a tiny local server with fake responses

from http.server import HTTPServer, BaseHTTPRequestHandler
import json

MOCK_SNAPSHOTS = [
    {"company":"Scaler","headline":"Become job-ready","audience":"job-seekers",
     "pricing":"premium","scraped_at":"2026-03-25T10:00:00"},
    {"company":"GeeksforGeeks","headline":"Learn to code","audience":"beginner",
     "pricing":"budget","scraped_at":"2026-03-25T10:05:00"},
    {"company":"Coursera","headline":"Learn from universities","audience":"intermediate",
     "pricing":"mid-tier","scraped_at":"2026-03-25T10:10:00"},
    {"company":"Udemy","headline":"Learn anything","audience":"intermediate",
     "pricing":"budget","scraped_at":"2026-03-25T10:15:00"},
]

MOCK_INSIGHTS = {
    "insights": "1. Positioning: Scaler targets job-seekers at premium pricing...\n2. Gaps: No platform targets advanced learners affordably\n3. Recommendation: Build cohort-based advanced courses at ₹5K",
    "gaps": ["No affordable advanced learning exists","Job-seeker segment overcrowded"],
    "profiles": MOCK_SNAPSHOTS
}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type","application/json")
        self.send_header("Access-Control-Allow-Origin","*")
        self.end_headers()
        if "/snapshots" in self.path:
            self.wfile.write(json.dumps(MOCK_SNAPSHOTS).encode())
        elif "/insights" in self.path:
            self.wfile.write(json.dumps(MOCK_INSIGHTS).encode())
        elif "/changes" in self.path:
            self.wfile.write(json.dumps([]).encode())
    def log_message(self, *args): pass

print("🚨 BACKUP SERVER running on http://localhost:8000")
HTTPServer(("", 8000), Handler).serve_forever()

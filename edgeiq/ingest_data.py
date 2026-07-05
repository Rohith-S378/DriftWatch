# ingest_data.py
# Run this AFTER P2's backend is running on http://localhost:8000

import json
import requests
import glob

BACKEND_URL = "http://localhost:8000/webhook/ingest"

def load_json_file(filepath):
    """Load a JSON file — handles both list and single object formats"""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return [data]
    return data

def ingest_all():
    json_files = glob.glob("data/*.json")

    if not json_files:
        print("❌ No JSON files found in data/ folder!")
        print("   Run your scrapers first or add mock data files.")
        return

    print(f"Found {len(json_files)} data files: {json_files}")
    print()

    total_sent = 0
    total_failed = 0

    for filepath in json_files:
        items = load_json_file(filepath)
        print(f"📁 Processing {filepath} — {len(items)} items")

        for item in items:
            company = item.get("company", "Unknown")
            try:
                response = requests.post(
    BACKEND_URL,
    json={
        "source_id": company.lower().replace(" ", "_"),
        "source_type": "competitor_scraper",
        "data": item
    },
    headers={"x-webhook-secret": "test"},
    timeout=60
)
                if response.status_code == 200:
                    result = response.json()
                    print(f"  ✅ {company} ingested — "
                          f"audience: {result.get('profile', {}).get('audience', '?')}, "
                          f"pricing: {result.get('profile', {}).get('pricing', '?')}")
                    total_sent += 1
                else:
                    print(f"  ❌ {company} failed — status {response.status_code}")
                    print(f"     Response: {response.text[:200]}")
                    total_failed += 1

            except requests.exceptions.ConnectionError:
                print(f"  ❌ Cannot connect to backend!")
                print(f"     Make sure P2 has started the server: uvicorn main:app --reload")
                print(f"     Stopping ingestion.")
                return

            except Exception as e:
                print(f"  ❌ {company} error: {e}")
                total_failed += 1

    print()
    print(f"═══════════════════════════════")
    print(f"  Done! Sent: {total_sent} | Failed: {total_failed}")
    print(f"═══════════════════════════════")

if __name__ == "__main__":
    ingest_all()

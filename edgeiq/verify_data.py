# verify_data.py — run this to check all data looks right

import json
import glob
import requests

print("=" * 50)
print("EdgeIQ Data Verification Report")
print("=" * 50)

# Check local JSON files
print("\n📁 LOCAL JSON FILES:")
for filepath in glob.glob("data/*.json"):
    with open(filepath) as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = [data]
    for item in data:
        company  = item.get("company", "?")
        headline = item.get("headline", "")
        fulltext = item.get("full_text", "")
        pricing  = item.get("pricing_text", "")
        print(f"\n  Company  : {company}")
        print(f"  Headline : {headline[:60] or '⚠️ EMPTY'}")
        print(f"  Text len : {len(fulltext)} chars {'✅' if len(fulltext) > 100 else '⚠️ TOO SHORT'}")
        print(f"  Pricing  : {pricing[:50] or '⚠️ EMPTY'}")

# Check backend
print("\n\n🔌 BACKEND CHECK:")
try:
    r = requests.get("http://localhost:8000/snapshots", timeout=5)
    snaps = r.json()
    print(f"  Snapshots in DB: {len(snaps)}")
    companies = set(s["company"] for s in snaps)
    print(f"  Companies: {', '.join(companies)}")
    for s in snaps[:4]:
        print(f"\n  [{s['company']}]")
        print(f"    Headline : {s.get('headline','')[:50]}")
        print(f"    Audience : {s.get('audience','?')}")
        print(f"    Scraped  : {s.get('scraped_at','?')[:16]}")
except Exception as e:
    print(f"  ❌ Cannot reach backend: {e}")

print("\n" + "=" * 50)

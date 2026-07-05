# scraper/scaler.py
# Scrapes Scaler.com for competitor intelligence

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # find utils.py

from utils import fetch_page, get_text, get_first_text, get_all_text, save_json, timestamp

COMPANY   = "Scaler"
URLS      = [
    "https://www.scaler.com/courses/",
    "https://www.scaler.com/data-science-course/",
]
OUTPUT    = "../data/scaler.json"

# ADD to bottom of each scraper (scaler.py, gfg.py etc.)
import requests

WEBHOOK_URL    = "http://localhost:8000/webhook/ingest"
WEBHOOK_SECRET = "super-secret-webhook-key-change-in-production"

def send_to_backend(company: str, data: dict):
    payload = {
        "source_id":   company.lower().replace(" ", "-"),  # e.g. "scaler"
        "source_type": "landing_page",
        "data": {
            "headline": data.get("headline", ""),
            "keywords": data.get("full_text", "").split()[:20],
            "plans": [
                {
                    "name":     "main",
                    "price":    data.get("pricing_text", ""),
                    "features": data.get("subheadlines", [])
                }
            ]
        }
    }
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            headers={"x-webhook-secret": WEBHOOK_SECRET},
            timeout=10
        )
        print(f"  ✅ Sent to backend: {response.status_code}")
        return response.json()
    except Exception as e:
        print(f"  ❌ Backend send failed: {e}")
        return None
def scrape_scaler(url: str) -> dict | None:
    """Scrape one Scaler page and return structured data"""

    print(f"\n🔍 Scraping {COMPANY}: {url}")
    soup = fetch_page(url)

    # ── FALLBACK: if site blocks us, return mock data ──────────────────────────
    if soup is None:
        print(f"  ⚠️  Using mock data for {COMPANY}")
        return {
            "company": COMPANY,
            "url": url,
            "scraped_at": timestamp(),
            "headline": "Become job-ready in 6 months",
            "subheadlines": ["Live mentorship", "Placement guarantee", "Career support"],
            "cta_buttons": ["Apply Now", "Book Free Trial"],
            "pricing_text": "1,20,000 premium EMI mentorship cohort",
            "full_text": (
                "Scaler job ready placement guarantee mentor live classes "
                "career switch hired salary hike cohort intermediate advanced "
                "one on one mentorship industry expert"
            ),
            "is_mock": True,
        }

    # ── HEADLINE ────────────────────────────────────────────────────────────────
    # Try multiple selectors — Scaler may use different class names
    headline = get_first_text(soup, [
        "h1",
        ".hero__title",
        ".hero-title",
        "[class*='hero'] h1",
        "[class*='banner'] h1",
    ])

    # ── SUBHEADLINES ────────────────────────────────────────────────────────────
    subheadlines = get_text(soup, "h2", limit=6)

    # ── CTA BUTTONS ─────────────────────────────────────────────────────────────
    # Find all links and buttons that look like call-to-action
    cta_elements = soup.select("a.btn, button, [class*='cta'], [class*='apply']")
    cta_buttons = []
    for el in cta_elements[:8]:
        text = el.get_text(strip=True)
        if text and len(text) < 50:           # CTAs are short text
            cta_buttons.append(text)

    # ── PRICING ─────────────────────────────────────────────────────────────────
    pricing_elements = soup.select(
        "[class*='price'], [class*='fee'], [class*='cost'], "
        "[class*='rupee'], [class*='amount']"
    )
    pricing_texts = []
    for el in pricing_elements[:5]:
        text = el.get_text(strip=True)
        if text:
            pricing_texts.append(text)
    pricing_text = " ".join(pricing_texts)[:500]

    # ── FULL TEXT ────────────────────────────────────────────────────────────────
    # Collect all meaningful text from the page
    full_text = get_all_text(soup, [
        "p",                    # paragraphs
        "li",                   # list items
        "h3", "h4",             # smaller headings
        "[class*='feature']",   # feature sections
        "[class*='benefit']",   # benefit sections
        "[class*='highlight']", # highlighted text
    ], max_chars=3000)

    # ── ASSEMBLE RESULT ──────────────────────────────────────────────────────────
    result = {
        "company":      COMPANY,
        "url":          url,
        "scraped_at":   timestamp(),
        "headline":     headline,
        "subheadlines": subheadlines,
        "cta_buttons":  cta_buttons,
        "pricing_text": pricing_text,
        "full_text":    full_text,
        "is_mock":      False,
    }

    # Print summary so you can see what was found
    print(f"  Headline    : {headline[:60] or '⚠️ empty'}")
    print(f"  Subheadlines: {len(subheadlines)} found")
    print(f"  CTAs        : {cta_buttons[:3]}")
    print(f"  Full text   : {len(full_text)} chars")

    return result


def run():
    print(f"\n{'='*50}")
    print(f"  SCRAPING: {COMPANY}")
    print(f"{'='*50}")

    all_results = []
    for url in URLS:
        result = scrape_scaler(url)
        if result:
            save_json(result, OUTPUT)
            send_to_backend("Scaler", result) 

    # Merge all pages into one record
    if all_results:
        merged = all_results[0].copy()
        # Combine full_text from all pages
        merged["full_text"] = " ".join(r["full_text"] for r in all_results)[:3000]
        save_json(merged, OUTPUT)
        print(f"\n✅ {COMPANY} scraping complete!")
    else:
        print(f"\n❌ No data collected for {COMPANY}")


if __name__ == "__main__":
    run()

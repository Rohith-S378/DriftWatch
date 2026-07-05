# scraper/coursera.py

import sys, os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils import fetch_page, get_text, get_first_text, get_all_text, save_json, timestamp

COMPANY = "Coursera"
URLS    = ["https://www.coursera.org/courses?query=programming"]
OUTPUT  = "../data/coursera.json"


def scrape_coursera(url: str) -> dict | None:
    print(f"\n🔍 Scraping {COMPANY}: {url}")
    soup = fetch_page(url)

    if soup is None:
        print(f"  ⚠️  Using mock data for {COMPANY}")
        return {
            "company": COMPANY,
            "url": url,
            "scraped_at": timestamp(),
            "headline": "Learn from top universities",
            "subheadlines": ["University certificates", "Self-paced learning"],
            "cta_buttons": ["Join for Free", "Start Learning"],
            "pricing_text": "$49 per month subscription university",
            "full_text": (
                "Coursera university certificate credential self paced flexible "
                "degree online subscription broad audience learn from home "
                "accredited programs professional development"
            ),
            "is_mock": True,
        }

    headline = get_first_text(soup, [
        "h1", "[class*='hero'] h1",
        "[class*='banner-title']",
        "[data-testid*='heading']",
    ])

    subheadlines = get_text(soup, "h2", limit=6)

    cta_elements = soup.select("button, a[class*='button'], [class*='cta']")
    cta_buttons  = [
        el.get_text(strip=True)
        for el in cta_elements[:8]
        if el.get_text(strip=True) and len(el.get_text(strip=True)) < 50
    ]

    # Coursera uses $ pricing
    pricing_elements = soup.select(
        "[class*='price'], [class*='subscription'], "
        "[aria-label*='price']"
    )
    pricing_text = " ".join(
        el.get_text(strip=True) for el in pricing_elements[:5]
    )[:500]

    full_text = get_all_text(soup, [
        "p", "li", "h3", "h4",
        "[class*='description']",
        "[class*='feature']",
        "[class*='benefit']",
    ], max_chars=3000)

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

    print(f"  Headline : {headline[:60] or '⚠️ empty'}")
    print(f"  Full text: {len(full_text)} chars")
    return result

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

def run():
    print(f"\n{'='*50}")
    print(f"  SCRAPING: {COMPANY}")
    print(f"{'='*50}")
    result = scrape_coursera(URLS[0])
    if result:
        save_json(result, OUTPUT)
        send_to_backend("Scaler", result) 


if __name__ == "__main__":
    run()

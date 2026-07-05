# scraper/utils.py
# Shared helper functions used by all scrapers

import requests
import bs4 # type: ignore
import json
import os
from datetime import datetime

# ─── HEADERS ──────────────────────────────────────────────────────────────────
# We send these with every request so websites think we are a real browser
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def fetch_page(url: str, timeout: int = 10) -> bs4.BeautifulSoup | None:
    """
    Fetch a webpage and return a BeautifulSoup object.
    Returns None if the request fails.
    """
    try:
        print(f"  Fetching: {url}")
        response = requests.get(url, headers=HEADERS, timeout=timeout)
        response.raise_for_status()           # raises error if status is 4xx/5xx

        # lxml is a fast HTML parser — falls back to html.parser if not installed
        try:
            soup = bs4.BeautifulSoup(response.text, "lxml")
        except Exception:
            soup = bs4.BeautifulSoup(response.text, "html.parser")

        print(f"  ✅ Got {len(response.text)} characters")
        return soup

    except requests.exceptions.ConnectionError:
        print(f"  ❌ Cannot connect to {url} — no internet or site is down")
        return None
    except requests.exceptions.Timeout:
        print(f"  ❌ Request timed out for {url}")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"  ❌ HTTP error {e.response.status_code} for {url}")
        return None
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return None


def get_text(soup: bs4.BeautifulSoup, selector: str, limit: int = 5) -> list[str]:
    """
    Find all elements matching a CSS selector and return their text.
    
    Example:
        get_text(soup, "h2")        → ["Learn Python", "Master Java", ...]
        get_text(soup, "p", limit=3) → first 3 paragraph texts
    """
    elements = soup.select(selector)          # select() uses CSS selectors
    texts = []
    for el in elements[:limit]:
        text = el.get_text(strip=True)        # strip=True removes whitespace
        if text:                              # only add if not empty
            texts.append(text)
    return texts


def get_first_text(soup: bs4.BeautifulSoup, selectors: list[str]) -> str:
    """
    Try multiple CSS selectors and return first text found.
    Useful when different pages use different class names.
    
    Example:
        get_first_text(soup, ["h1", ".hero-title", "#main-heading"])
    """
    for selector in selectors:
        el = soup.select_one(selector)        # select_one = find first match
        if el:
            text = el.get_text(strip=True)
            if text:
                return text
    return ""                                 # return empty string if nothing found


def get_all_text(soup: bs4.BeautifulSoup, selectors: list[str],
                 max_chars: int = 3000) -> str:
    """
    Collect text from multiple selectors and join into one string.
    Truncated to max_chars to avoid sending huge text to the AI.
    """
    all_text = []
    for selector in selectors:
        elements = soup.select(selector)
        for el in elements:
            text = el.get_text(strip=True)
            if text and len(text) > 20:       # skip very short snippets
                all_text.append(text)

    combined = " ".join(all_text)
    return combined[:max_chars]


def save_json(data: dict, filepath: str):
    """
    Save scraped data to a JSON file.
    Creates the data/ folder if it doesn't exist.
    """
    os.makedirs(os.path.dirname(filepath), exist_ok=True)

    # Load existing data if file exists (so we can append)
    existing = []
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                existing = json.load(f)
            if isinstance(existing, dict):
                existing = [existing]
        except Exception:
            existing = []

    existing.append(data)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"  💾 Saved to {filepath}")


def timestamp() -> str:
    """Return current UTC time as ISO string"""
    return datetime.utcnow().isoformat()
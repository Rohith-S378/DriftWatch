import re
from typing import Optional, Set

def extract_price(text: str) -> Optional[float]:
    """Extract numeric price from '₹499/month', '$10.99', etc."""
    if not text:
        return None
    # Remove commas and look for currency + number
    text = text.replace(",", "")
    match = re.search(r'[\$₹£€]\s*(\d+(?:\.\d+)?)', text)
    if match:
        return float(match.group(1))
    # fallback: any number
    match = re.search(r'\d+(?:\.\d+)?', text)
    if match:
        return float(match.group(1))
    return None


def extract_currency(text: str) -> str:
    """Return currency code based on symbol."""
    text = text.upper()
    if "₹" in text or "INR" in text:
        return "INR"
    if "$" in text or "USD" in text:
        return "USD"
    if "£" in text or "GBP" in text:
        return "GBP"
    if "€" in text or "EUR" in text:
        return "EUR"
    return "INR"  # default


def extract_keywords(text: str) -> Set[str]:
    """Return set of tracked AI/product keywords found in text."""
    if not text:
        return set()
    text_lower = text.lower()
    tracked = {
        "affordable", "premium", "ai", "exam", "skills",
        "coaching", "unlimited", "hints", "pro", "starter",
        "enterprise", "basic", "free", "trial", "discount",
    }
    return {kw for kw in tracked if kw in text_lower}


def normalize_headline(text: str) -> str:
    """Normalise for reliable headline comparison."""
    if not text:
        return ""
    # Remove punctuation, collapse whitespace, lowercase
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text.strip().lower())
    return text
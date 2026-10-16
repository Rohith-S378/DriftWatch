"""
Company Website Profiler.
Crawls a company's website (landing page + bounded key internal links),
extracts business signals (products, customer problems, industry, features, keywords, pricing),
and constructs a structured CompanyProfile distinguishing directly extracted facts from model inferences.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlparse, urljoin
import re

import aiohttp
from bs4 import BeautifulSoup

from app.services.url_validator import validate_crawl_url, URLValidationError
from app.services.crawler import CompetitorCrawler

logger = logging.getLogger(__name__)

# Bounded crawling constraints
MAX_PAGES_TO_PROFILE = 4
PAGE_TIMEOUT_SECONDS = 15
MAX_PAGE_BYTES = 1_000_000  # 1MB per page response limit

# Common page patterns relevant for business profiling
PRIORITY_LINK_PATTERNS = [
    re.compile(r"pricing", re.I),
    re.compile(r"product(s)?", re.I),
    re.compile(r"feature(s)?", re.I),
    re.compile(r"about", re.I),
    re.compile(r"solution(s)?", re.I),
]


def normalize_domain(url: str) -> str:
    """Normalize a URL to its base domain (lowercase, strip 'www.')."""
    parsed = urlparse(url.strip())
    netloc = parsed.netloc or parsed.path.split("/")[0]
    # Remove port if present
    netloc = netloc.split(":")[0].lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


class CompanyProfiler:
    """Crawls accessible public pages of a company to build a structured profile."""

    def __init__(self):
        self.crawler_helper = CompetitorCrawler()

    async def profile_website(self, url: str, allow_local: bool = False) -> Dict[str, Any]:
        """
        Build a structured company profile from a user-supplied website URL.
        """
        # 1. URL validation & SSRF check
        safe_url = validate_crawl_url(url, allow_local=allow_local)
        domain = normalize_domain(safe_url)

        pages_crawled = []
        source_urls = []
        pages_to_crawl = [safe_url]
        visited_urls: Set[str] = set()

        raw_texts: List[str] = []
        headlines: List[str] = []
        pricing_data: List[Dict[str, Any]] = []
        features_found: Set[str] = set()
        meta_descriptions: List[str] = []

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DriftWatch/2.0 CompetitorDiscovery"
        }

        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=PAGE_TIMEOUT_SECONDS)) as session:
            while pages_to_crawl and len(pages_crawled) < MAX_PAGES_TO_PROFILE:
                current_url = pages_to_crawl.pop(0)
                norm_current = current_url.rstrip("/")
                if norm_current in visited_urls:
                    continue
                visited_urls.add(norm_current)

                try:
                    # Validate each subsequent link as well for SSRF safety
                    checked_url = validate_crawl_url(current_url, allow_local=allow_local)
                except URLValidationError as exc:
                    logger.warning(f"Skipping link {current_url} due to safety check: {exc}")
                    continue

                try:
                    async with session.get(checked_url, headers=headers) as resp:
                        if resp.status != 200:
                            continue
                        
                        # Limit read size
                        content_bytes = await resp.content.read(MAX_PAGE_BYTES)
                        html_text = content_bytes.decode(errors="replace")
                        
                        soup = BeautifulSoup(html_text, "html.parser")
                        pages_crawled.append(checked_url)
                        source_urls.append(checked_url)

                        # Extract metadata
                        meta_desc = soup.find("meta", attrs={"name": re.compile(r"description", re.I)})
                        if meta_desc and meta_desc.get("content"):
                            meta_descriptions.append(meta_desc.get("content").strip())

                        meta_og = soup.find("meta", attrs={"property": "og:description"})
                        if meta_og and meta_og.get("content"):
                            meta_descriptions.append(meta_og.get("content").strip())

                        # Headline
                        hl = self.crawler_helper._extract_headline(soup)
                        if hl:
                            headlines.append(hl)

                        # Pricing
                        plans = self.crawler_helper._extract_pricing(soup)
                        if plans:
                            pricing_data.extend(plans)

                        # Features
                        feats = self.crawler_helper._extract_features(soup)
                        if feats:
                            features_found.update(feats)

                        # Collect readable text
                        text_chunks = [t.strip() for t in soup.stripped_strings if len(t.strip()) > 3]
                        raw_texts.append(" ".join(text_chunks[:500]))

                        # Discover links for bounded profiling (same domain only)
                        if len(pages_crawled) < MAX_PAGES_TO_PROFILE:
                            for a_tag in soup.find_all("a", href=True):
                                href = a_tag["href"].strip()
                                full_link = urljoin(checked_url, href)
                                link_domain = normalize_domain(full_link)
                                if link_domain == domain and full_link.rstrip("/") not in visited_urls:
                                    # Prioritize business pages
                                    if any(pattern.search(full_link) for pattern in PRIORITY_LINK_PATTERNS):
                                        if full_link not in pages_to_crawl:
                                            pages_to_crawl.append(full_link)
                except Exception as exc:
                    logger.warning(f"Error profiling page {current_url}: {exc}")
                    continue

        if not pages_crawled:
            raise RuntimeError(f"Could not fetch or parse any accessible pages for {url}")

        combined_text = " ".join(raw_texts)
        company_name = self._infer_company_name(domain, headlines, soup if 'soup' in locals() else None)
        
        # Extract features and keywords
        extracted_keywords = sorted(list(self._extract_keywords(combined_text)))
        features_list = sorted(list(features_found))

        # Build descriptions and inferences
        description = meta_descriptions[0] if meta_descriptions else (headlines[0] if headlines else "")
        industry_cat, target_customers, problems_addressed = self._infer_business_signals(
            combined_text, headlines, description
        )

        # Detect pricing model
        pricing_model = "Free / Freemium" if any("free" in p.get("name", "").lower() or "$0" in p.get("price", "") for p in pricing_data) else ("Subscription / Tiered" if pricing_data else "Unknown / Contact Sales")

        profile = {
            "company_name": company_name,
            "website": safe_url,
            "normalized_domain": domain,
            "company_description": description or f"{company_name} online platform",
            "products_and_services": headlines[:3] if headlines else [f"{company_name} Core Offering"],
            "industry_category": industry_cat,
            "target_customers": target_customers,
            "customer_problems": problems_addressed,
            "features_and_value_props": features_list[:8],
            "pricing_model": pricing_model,
            "pricing_plans": pricing_data[:5],
            "geographic_market": "Global (online/cloud)",
            "keywords": extracted_keywords[:15],
            "source_urls": source_urls,
            "pages_crawled_count": len(pages_crawled),
            "confidence_score": round(min(1.0, 0.4 + (len(pages_crawled) * 0.15) + (0.2 if pricing_data else 0.0) + (0.1 if description else 0.0)), 2),
            "missing_fields": [
                f for f, v in [
                    ("pricing", bool(pricing_data)),
                    ("meta_description", bool(meta_descriptions)),
                    ("features", bool(features_list)),
                ] if not v
            ]
        }
        return profile

    def _infer_company_name(self, domain: str, headlines: List[str], soup: Optional[BeautifulSoup]) -> str:
        """Infer company name from domain or page title/OG tags."""
        if soup:
            og_site = soup.find("meta", attrs={"property": "og:site_name"})
            if og_site and og_site.get("content"):
                return og_site.get("content").strip()
            title = soup.find("title")
            if title and title.string:
                title_parts = re.split(r"[-|•—:]", title.string)
                if len(title_parts) > 1:
                    candidate = title_parts[-1].strip()
                    if 2 <= len(candidate) <= 25:
                        return candidate

        # Fallback to domain root
        root = domain.split(".")[0]
        return root.capitalize()

    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract domain and marketing keywords from combined text."""
        words = re.findall(r"\b[a-zA-Z]{3,15}\b", text.lower())
        stopwords = {
            "this", "that", "with", "from", "your", "have", "more", "will", "about",
            "home", "page", "contact", "privacy", "terms", "rights", "reserved", "click",
            "copyright", "login", "signup", "sign", "terms", "policy", "cookies"
        }
        freq: Dict[str, int] = {}
        for w in words:
            if w not in stopwords:
                freq[w] = freq.get(w, 0) + 1
        
        # Sort by frequency
        sorted_words = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        return {w for w, count in sorted_words[:25]}

    def _infer_business_signals(
        self, text: str, headlines: List[str], description: str
    ) -> tuple[str, List[str], List[str]]:
        """
        Classify industry category, target audience, and customer problems addressed.
        """
        combined = f"{description} {' '.join(headlines)} {text}".lower()

        # Industry Classification
        industry = "Technology & Software"
        if any(w in combined for w in ["exam", "coaching", "learning", "course", "quiz", "certification", "edtech", "tutor", "student"]):
            industry = "Education & EdTech"
        elif any(w in combined for w in ["payment", "banking", "finance", "crypto", "invest", "fintech", "wallet", "credit"]):
            industry = "Financial Services & FinTech"
        elif any(w in combined for w in ["health", "medical", "patient", "clinic", "wellness", "doctor", "telehealth"]):
            industry = "Healthcare & HealthTech"
        elif any(w in combined for w in ["ecommerce", "shop", "cart", "checkout", "retail", "store"]):
            industry = "E-Commerce & Retail"
        elif any(w in combined for w in ["dev", "api", "cloud", "infra", "database", "security", "developer"]):
            industry = "Developer Tools & Cloud Infrastructure"

        # Target Customers
        targets = []
        if any(w in combined for w in ["enterprise", "organization", "corporate", "team", "b2b"]):
            targets.append("Enterprises & Organizations")
        if any(w in combined for w in ["student", "learner", "individual", "consumer", "job seeker"]):
            targets.append("Individual Learners / Professionals")
        if any(w in combined for w in ["startup", "small business", "smb", "agency"]):
            targets.append("Startups & SMBs")
        if not targets:
            targets.append("General Commercial Customers")

        # Problems Addressed
        problems = []
        if "exam" in combined or "certification" in combined:
            problems.append("Exam readiness and credential preparation")
        if "ai" in combined or "automation" in combined:
            problems.append("Manual effort reduction through AI automation")
        if "career" in combined or "placement" in combined:
            problems.append("Career development and job placement acceleration")
        if "cost" in combined or "price" in combined or "affordable" in combined:
            problems.append("High service cost and affordability barriers")
        if not problems:
            problems.append("Market intelligence and performance optimization")

        return industry, targets, problems

profiler = CompanyProfiler()

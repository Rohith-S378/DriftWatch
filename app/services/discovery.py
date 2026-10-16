"""
Competitor Discovery Engine.
Orchestrates:
- Query generation from company profile
- Candidate search retrieval via configured provider
- Candidate deduplication and domain normalization
- Candidate verification via crawler
- Explainable ranking, match scoring, and classification (direct / indirect / adjacent)
- Explicit representation of missing evidence
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, List, Optional, Any, Set
from urllib.parse import urlparse

from app.services.profiler import normalize_domain
from app.services.search_providers import SearchProviderBase, get_search_provider
from app.services.crawler import CompetitorCrawler
from app.services.url_validator import validate_crawl_url, URLValidationError

logger = logging.getLogger(__name__)


class CompetitorDiscoveryEngine:
    """Discovers, verifies, ranks, and classifies competitor candidates."""

    def __init__(self, search_provider: Optional[SearchProviderBase] = None):
        self.search_provider = search_provider or get_search_provider()
        self.crawler = CompetitorCrawler()

    def generate_search_queries(self, profile: Dict[str, Any]) -> List[str]:
        """
        Generate targeted search queries across product, industry, audience, and alternatives.
        """
        company_name = profile.get("company_name", "")
        industry = profile.get("industry_category", "")
        keywords = profile.get("keywords", [])[:4]
        problems = profile.get("customer_problems", [])[:2]

        kw_str = " ".join(keywords)

        queries = [
            f"top competitors to {company_name} {industry}",
            f"alternatives to {company_name} {kw_str}",
            f"best companies offering {industry} {kw_str}",
            f"{industry} solutions for {problems[0] if problems else 'online customers'}",
        ]
        return [q.strip() for q in queries if q.strip()]

    async def discover_candidates(
        self, profile: Dict[str, Any], allow_local: bool = False, max_candidates: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Run the complete discovery workflow for a profile.
        """
        source_domain = profile.get("normalized_domain", "")
        queries = self.generate_search_queries(profile)

        # 1. Gather raw candidates from search queries
        raw_items = []
        for q in queries:
            try:
                items = await self.search_provider.search(q, max_results=5)
                raw_items.extend(items)
            except Exception as exc:
                logger.warning(f"Search provider failed on query '{q}': {exc}")

        # 2. Normalize and deduplicate by domain
        deduped_candidates: Dict[str, Dict[str, Any]] = {}
        for item in raw_items:
            try:
                domain = normalize_domain(item.url)
            except Exception:
                continue

            # Exclude own domain and common non-competitor aggregator platforms
            ignored_domains = {
                source_domain,
                "google.com", "bing.com", "duckduckgo.com", "youtube.com",
                "wikipedia.org", "linkedin.com", "twitter.com", "x.com",
                "facebook.com", "reddit.com", "github.com", "medium.com"
            }
            if domain in ignored_domains or not domain:
                continue

            if domain not in deduped_candidates:
                deduped_candidates[domain] = {
                    "candidate_name": self._extract_candidate_name(item.title, domain),
                    "website_url": item.url,
                    "normalized_domain": domain,
                    "search_snippet": item.snippet,
                    "source_urls": [item.url],
                    "raw_titles": [item.title],
                }
            else:
                deduped_candidates[domain]["source_urls"].append(item.url)
                deduped_candidates[domain]["raw_titles"].append(item.title)

        candidate_list = list(deduped_candidates.values())[:max_candidates]

        # 3. Verify candidates and extract verified business evidence (parallel)
        verified_results = await asyncio.gather(
            *[
                self._verify_and_score_candidate(cand, profile, allow_local=allow_local)
                for cand in candidate_list
            ]
        )

        # 4. Rank candidates by match score descending
        verified_results.sort(key=lambda c: c["match_score"], reverse=True)
        return verified_results

    async def _verify_and_score_candidate(
        self, candidate: Dict[str, Any], profile: Dict[str, Any], allow_local: bool = False
    ) -> Dict[str, Any]:
        """
        Verify candidate website with crawler and calculate explainable match scores.
        """
        target_url = candidate["website_url"]
        domain = candidate["normalized_domain"]

        # Attempt verification crawl
        crawl_res = await self.crawler.crawl(
            source_id=f"verify_{domain}",
            url=target_url,
            allow_local=allow_local,
        )

        verified = crawl_res.success
        extracted_headline = crawl_res.headline if verified else ""
        extracted_keywords = set(crawl_res.keywords) if verified else set()
        extracted_pricing = crawl_res.pricing if verified else []
        extracted_features = crawl_res.features if verified else []

        profile_keywords = set(profile.get("keywords", []))
        profile_industry = profile.get("industry_category", "")
        profile_problems = profile.get("customer_problems", [])

        # Explainable multi-factor scoring (weights sum to 100)
        # Factor 1: Keyword & Feature Overlap (35 pts)
        kw_overlap = len(extracted_keywords.intersection(profile_keywords))
        kw_score = min(35, kw_overlap * 7)

        # Factor 2: Snippet / Content relevance (25 pts)
        snippet_text = f"{candidate.get('search_snippet', '')} {extracted_headline}".lower()
        snippet_hits = sum(1 for kw in profile_keywords if kw.lower() in snippet_text)
        snippet_score = min(25, snippet_hits * 5)

        # Factor 3: Industry & Category alignment (20 pts)
        industry_score = 0
        if any(term in snippet_text for term in profile_industry.lower().split()):
            industry_score = 20
        elif any(term in snippet_text for term in ["platform", "software", "solution", "online"]):
            industry_score = 10

        # Factor 4: Business model / pricing signal (20 pts)
        pricing_score = 0
        if extracted_pricing:
            pricing_score = 20
        elif "pricing" in snippet_text or "plan" in snippet_text or "$" in snippet_text or "free" in snippet_text:
            pricing_score = 10

        total_score = kw_score + snippet_score + industry_score + pricing_score
        # Baseline minimum for returned search items
        total_score = max(total_score, 20)

        # Explainable Classification
        if total_score >= 70:
            classification = "direct"
            classification_reason = "High overlap in core offerings, target audience, and business models."
        elif total_score >= 45:
            classification = "indirect"
            classification_reason = "Overlapping industry and problem domain, but offers different delivery models or product scope."
        else:
            classification = "adjacent"
            classification_reason = "Adjacent industry player or complementary service provider with potential market overlap."

        # Missing evidence
        missing_evidence = []
        if not verified:
            missing_evidence.append(f"Direct site verification unavailable ({crawl_res.error or 'unreachable'})")
        if not extracted_pricing:
            missing_evidence.append("Explicit pricing plans not detected on landing page")
        if not extracted_features:
            missing_evidence.append("Structured feature matrix not found")

        explanation = (
            f"Match Score {total_score}/100. {classification_reason} "
            f"Identified {kw_overlap} shared domain keywords and verified {len(extracted_pricing)} pricing plans."
        )

        return {
            "candidate_name": candidate["candidate_name"],
            "website_url": target_url,
            "normalized_domain": domain,
            "match_score": total_score,
            "match_explanation": explanation,
            "classification": classification,
            "classification_reason": classification_reason,
            "is_verified": verified,
            "verification_error": crawl_res.error if not verified else None,
            "extracted_headline": extracted_headline,
            "extracted_pricing_count": len(extracted_pricing),
            "evidence": {
                "shared_keywords": sorted(list(extracted_keywords.intersection(profile_keywords))),
                "search_snippet": candidate.get("search_snippet", ""),
                "source_urls": candidate["source_urls"],
            },
            "missing_evidence": missing_evidence,
        }

    def _extract_candidate_name(self, title: str, domain: str) -> str:
        """Derive a clean company name from page title or domain."""
        if title:
            # Often formatted as "CompanyName: Tagline" or "CompanyName - Slogan"
            parts = [p.strip() for p in title.replace("|", "-").replace(":", "-").split("-")]
            if parts and 2 <= len(parts[0]) <= 30:
                return parts[0]
        # Domain fallback
        root = domain.split(".")[0]
        return root.capitalize()

discovery_engine = CompetitorDiscoveryEngine()

"""
analyzer.py — P4 AI/Insight Lead
Classifies and scores all EdTech competitor constraints from P2's API data.
"""

from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from typing import Any

# ──────────────────────────────────────────────
# Data Structures
# ──────────────────────────────────────────────

@dataclass
class PricingProfile:
    base_price: float = 0.0
    discount_pct: float = 0.0
    has_emi: bool = False
    free_paid_ratio: float = 0.0          # 0–1, fraction of free content
    price_change_pct: float = 0.0         # % change from previous snapshot
    score: float = 0.0                    # 0–100 competitiveness score

@dataclass
class CourseProfile:
    avg_duration_weeks: float = 0.0
    num_modules: int = 0
    beginner_ratio: float = 0.0           # 0–1
    has_certification: bool = False
    live_ratio: float = 0.0              # live vs recorded
    has_doubt_solving: bool = False
    has_assignments: bool = False
    popular_courses: list[str] = field(default_factory=list)
    duration_change_pct: float = 0.0
    score: float = 0.0

@dataclass
class EngagementProfile:
    ads_frequency_weekly: float = 0.0
    social_posts_weekly: float = 0.0
    youtube_videos_monthly: float = 0.0
    youtube_subscribers: int = 0
    youtube_avg_views: float = 0.0
    youtube_comments_avg: float = 0.0
    review_rating: float = 0.0
    num_reviews: int = 0
    students_enrolled: int = 0
    score: float = 0.0

@dataclass
class RetentionProfile:
    referral_program: bool = False
    rewards_offered: bool = False
    free_trial: bool = False
    website_changes_count: int = 0        # # of UX/content changes detected
    discontinuity_signals: int = 0        # negative UX changes
    score: float = 0.0

@dataclass
class CompanyProfile:
    name: str = ""
    domain: str = ""                      # competitive_exam | technical | college_school
    pricing: PricingProfile = field(default_factory=PricingProfile)
    courses: CourseProfile = field(default_factory=CourseProfile)
    engagement: EngagementProfile = field(default_factory=EngagementProfile)
    retention: RetentionProfile = field(default_factory=RetentionProfile)
    student_intake_change_pct: float = 0.0   # overall intake delta
    overall_score: float = 0.0

# ──────────────────────────────────────────────
# Scorer helpers
# ──────────────────────────────────────────────

def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def score_pricing(p: PricingProfile) -> float:
    s = 50.0
    s += min(p.discount_pct * 1.2, 20)         # discounts attract students
    s += 10 if p.has_emi else 0
    s += p.free_paid_ratio * 15                 # free content drives funnel
    s -= max(p.price_change_pct, 0) * 0.5      # price hike hurts
    s += max(-p.price_change_pct, 0) * 0.8     # price cut helps
    return _clamp(s)


def score_courses(c: CourseProfile) -> float:
    s = 40.0
    s += 10 if c.has_certification else 0
    s += c.live_ratio * 15
    s += 10 if c.has_doubt_solving else 0
    s += 5 if c.has_assignments else 0
    s += min(c.num_modules * 0.5, 10)
    # Optimal duration ~8–16 weeks
    dur = c.avg_duration_weeks
    dur_score = 10 - abs(dur - 12) * 0.5
    s += _clamp(dur_score, 0, 10)
    s += max(-c.duration_change_pct, 0) * 0.3  # shortening courses helps intake
    return _clamp(s)


def score_engagement(e: EngagementProfile) -> float:
    s = 30.0
    s += min(e.ads_frequency_weekly * 2, 15)
    s += min(e.social_posts_weekly * 1.5, 12)
    s += min(e.youtube_videos_monthly * 0.8, 10)
    s += min(e.review_rating * 4, 20)
    s += min(e.youtube_avg_views / 5000, 8)
    s += min(e.youtube_comments_avg / 100, 5)
    return _clamp(s)


def score_retention(r: RetentionProfile) -> float:
    s = 40.0
    s += 15 if r.referral_program else 0
    s += 10 if r.rewards_offered else 0
    s += 10 if r.free_trial else 0
    s -= r.discontinuity_signals * 5           # bad UX signals hurt
    s += min(r.website_changes_count * 2, 10)  # active improvement helps
    return _clamp(s)


def compute_overall(cp: CompanyProfile) -> float:
    return _clamp(
        cp.pricing.score * 0.25
        + cp.courses.score * 0.30
        + cp.engagement.score * 0.25
        + cp.retention.score * 0.20
    )

# ──────────────────────────────────────────────
# Main Analyzer
# ──────────────────────────────────────────────

class EdTechAnalyzer:
    """
    Receives raw snapshot data (from P2) and returns scored CompanyProfile objects.
    """

    DOMAIN_KEYS = ("competitive_exam", "technical", "college_school")

    def analyze(self, snapshot: dict[str, Any]) -> CompanyProfile:
        """Convert a single company snapshot dict into a scored CompanyProfile."""
        cp = CompanyProfile()
        cp.name = snapshot.get("company_name", "Unknown")
        cp.domain = snapshot.get("domain", "technical")
        cp.student_intake_change_pct = snapshot.get("student_intake_change_pct", 0.0)

        # ── Pricing ──
        pr = snapshot.get("pricing", {})
        cp.pricing = PricingProfile(
            base_price=pr.get("base_price", 0),
            discount_pct=pr.get("discount_pct", 0),
            has_emi=pr.get("has_emi", False),
            free_paid_ratio=pr.get("free_paid_ratio", 0),
            price_change_pct=pr.get("price_change_pct", 0),
        )
        cp.pricing.score = score_pricing(cp.pricing)

        # ── Courses ──
        co = snapshot.get("courses", {})
        cp.courses = CourseProfile(
            avg_duration_weeks=co.get("avg_duration_weeks", 0),
            num_modules=co.get("num_modules", 0),
            beginner_ratio=co.get("beginner_ratio", 0.5),
            has_certification=co.get("has_certification", False),
            live_ratio=co.get("live_ratio", 0),
            has_doubt_solving=co.get("has_doubt_solving", False),
            has_assignments=co.get("has_assignments", False),
            popular_courses=co.get("popular_courses", []),
            duration_change_pct=co.get("duration_change_pct", 0),
        )
        cp.courses.score = score_courses(cp.courses)

        # ── Engagement ──
        en = snapshot.get("engagement", {})
        cp.engagement = EngagementProfile(
            ads_frequency_weekly=en.get("ads_frequency_weekly", 0),
            social_posts_weekly=en.get("social_posts_weekly", 0),
            youtube_videos_monthly=en.get("youtube_videos_monthly", 0),
            youtube_subscribers=en.get("youtube_subscribers", 0),
            youtube_avg_views=en.get("youtube_avg_views", 0),
            youtube_comments_avg=en.get("youtube_comments_avg", 0),
            review_rating=en.get("review_rating", 0),
            num_reviews=en.get("num_reviews", 0),
            students_enrolled=en.get("students_enrolled", 0),
        )
        cp.engagement.score = score_engagement(cp.engagement)

        # ── Retention ──
        re = snapshot.get("retention", {})
        cp.retention = RetentionProfile(
            referral_program=re.get("referral_program", False),
            rewards_offered=re.get("rewards_offered", False),
            free_trial=re.get("free_trial", False),
            website_changes_count=re.get("website_changes_count", 0),
            discontinuity_signals=re.get("discontinuity_signals", 0),
        )
        cp.retention.score = score_retention(cp.retention)

        cp.overall_score = compute_overall(cp)
        return cp

    def analyze_batch(self, snapshots: list[dict]) -> list[CompanyProfile]:
        return [self.analyze(s) for s in snapshots]

    def to_dict(self, cp: CompanyProfile) -> dict:
        return asdict(cp)

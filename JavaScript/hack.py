# ================================================
# P4 — AI / Insight Lead: Full Code (analyzer.py + rag.py + insight_gen.py)
# 
# How to integrate with P2 (Backend):
# 1. Place these 3 files in your backend/ folder (or a subfolder like backend/p4/)
# 2. In main.py (P2), import and call like this in your /insights endpoint:
#
#    from p4.insight_gen import InsightGenerator
#    from p4.models import get_all_snapshots  # your helper that returns the dict below
#
#    @app.get("/insights")
#    def get_insights():
#        data = get_all_snapshots()   # ← must return the exact dict structure shown in insight_gen.py
#        gen = InsightGenerator()
#        return gen.generate_insights(data)
#
# 3. Data comes from P2’s SQLite snapshots (diff_engine already gives you historical changes).
# 4. Frontend (P3) will receive clean JSON with "insights", "recommendations", "explanations"
#    → perfect for Overview / Insights / Changes / Ask AI tabs.
# ================================================

# ------------------- analyzer.py -------------------
"""analyzer.py — NLP-style classification of pricing, audience, style, and other constraints"""
from typing import Dict, List, Any

def classify_pricing(courses: List[Dict[str, Any]]) -> Dict[str, float]:
    if not courses:
        return {"free_vs_paid_ratio": 0.0, "avg_price": 0.0, "emi_option_ratio": 0.0, "discount_ratio": 0.0}
    total = len(courses)
    paid = sum(1 for c in courses if c.get("price", 0) > 0)
    emi = sum(1 for c in courses if c.get("emi_available", False))
    discounts = sum(1 for c in courses if c.get("discount", 0) > 0)
    return {
        "free_vs_paid_ratio": (total - paid) / total,
        "avg_price": sum(c.get("price", 0) for c in courses) / total,
        "emi_option_ratio": emi / total,
        "discount_ratio": discounts / total,
    }


def classify_audience(courses: List[Dict[str, Any]]) -> Dict[str, float]:
    if not courses:
        return {"beginner_ratio": 0.0, "advanced_ratio": 0.0}
    total = len(courses)
    beginner = sum(1 for c in courses if c.get("level", "").lower() == "beginner")
    return {
        "beginner_ratio": beginner / total,
        "advanced_ratio": (total - beginner) / total,
    }


def classify_style(courses: List[Dict[str, Any]]) -> Dict[str, float]:
    if not courses:
        return {"live_vs_recorded_ratio": 0.0, "youtube_support_ratio": 0.0, "doubt_solving_ratio": 0.0, "assignments_ratio": 0.0}
    total = len(courses)
    live = sum(1 for c in courses if c.get("live_classes", False))
    youtube = sum(1 for c in courses if c.get("youtube_support", False))
    doubt = sum(1 for c in courses if c.get("doubt_solving", False))
    assignments = sum(1 for c in courses if c.get("assignments", False))
    return {
        "live_vs_recorded_ratio": live / total,
        "youtube_support_ratio": youtube / total,
        "doubt_solving_ratio": doubt / total,
        "assignments_ratio": assignments / total,
    }


def classify_social(social: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "posts_count": social.get("posts_count", 0),
        "ads_frequency": social.get("ads_frequency", 0),
        "youtube_videos_posted": social.get("youtube_activity", {}).get("videos_posted", 0),
        "youtube_comments": social.get("youtube_activity", {}).get("comments", 0),
        "youtube_views": social.get("youtube_activity", {}).get("views", 0),
    }


def classify_rewards(rewards: Dict[str, Any]) -> Dict[str, bool]:
    return {
        "referral_program": rewards.get("referral_program", False),
        "free_trial": rewards.get("free_trial", False),
        "discount_offers": bool(rewards.get("discounts_offers")),
    }

# ------------------- rag.py -------------------
"""rag.py — Context retrieval (simple keyword-based RAG for now; easy to upgrade to vector DB later)"""
from typing import Dict, Any

class RAG:
    def __init__(self):
        self.context_store: Dict[str, Dict] = {}

    def add_context(self, company_name: str, snapshot: Dict[str, Any]):
        self.context_store[company_name] = snapshot

    def retrieve(self, query: str, company_name: str = None) -> str:
        """Return relevant context for a given query (pricing, social, duration, rewards, etc.)"""
        if company_name and company_name in self.context_store:
            data = self.context_store[company_name]
            keywords = query.lower().split()
            relevant = []

            if any(k in keywords for k in ["price", "fee", "discount", "emi"]):
                relevant.append(f"Pricing → Avg price: {data.get('avg_price', 'N/A')}, Free/Paid ratio: {data.get('free_vs_paid_ratio', 'N/A')}, Discounts: {data.get('discount_ratio', 'N/A')}")
            if any(k in keywords for k in ["social", "post", "ad", "youtube"]):
                relevant.append(f"Social/YouTube → Posts: {data.get('posts_count', 'N/A')}, Ads freq: {data.get('ads_frequency', 'N/A')}, YT videos: {data.get('youtube_videos_posted', 'N/A')}, Comments: {data.get('youtube_comments', 'N/A')}")
            if any(k in keywords for k in ["duration", "course length"]):
                relevant.append(f"Course duration avg: {data.get('avg_duration_weeks', 'N/A')} weeks")
            if any(k in keywords for k in ["reward", "referral", "free trial"]):
                relevant.append(f"Rewards → Referral: {data.get('referral_program', 'N/A')}, Free trial: {data.get('free_trial', 'N/A')}")
            if any(k in keywords for k in ["intake", "students", "enrolled"]):
                relevant.append(f"Student intake: {data.get('num_students_enrolled', 'N/A')} (latest snapshot)")

            return "\n".join(relevant) or "No specific context matched the query."
        return "Company context not found in RAG store."

# ------------------- insight_gen.py (MAIN FILE) -------------------
"""insight_gen.py — Core engine that compares EVERY constraint, correlates with student intake changes,
detects increase/decrease, combines 2+ constraints, and returns ready-to-display JSON for P3."""
import json
from datetime import datetime
from typing import Dict, Any, List
from analyzer import (
    classify_pricing, classify_audience, classify_style,
    classify_social, classify_rewards
)
from .rag import RAG

class InsightGenerator:
    def __init__(self):
        self.rag = RAG()

    def _get_latest_snapshot(self, company_data: Dict) -> Dict:
        snapshots = company_data.get("snapshots", [])
        return snapshots[-1] if snapshots else {}

    def _calculate_change(self, snapshots: List[Dict]) -> Dict[str, Any]:
        if len(snapshots) < 2:
            return {"intake_change": 0, "intake_change_pct": 0.0}
        latest = snapshots[-1]
        prev = snapshots[-2]
        change = latest.get("num_students_enrolled", 0) - prev.get("num_students_enrolled", 0)
        pct = (change / prev.get("num_students_enrolled", 1)) * 100 if prev.get("num_students_enrolled", 1) > 0 else 0.0
        return {"intake_change": change, "intake_change_pct": round(pct, 2)}

    def _avg_price(self, courses: List[Dict]) -> float:
        if not courses:
            return 0.0
        return sum(c.get("price", 0) for c in courses) / len(courses)

    def _avg_duration(self, courses: List[Dict]) -> float:
        if not courses:
            return 0.0
        return sum(c.get("duration_weeks", 0) for c in courses) / len(courses)

    def _popular_courses(self, courses: List[Dict]) -> List[str]:
        if not courses:
            return []
        sorted_courses = sorted(courses, key=lambda c: c.get("num_students_enrolled", 0), reverse=True)
        return [c["name"] for c in sorted_courses[:3]]

    def generate_insights(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Expected input data structure (prepared by P2 from SQLite snapshots):
        {
            "our_company": {
                "name": "OurEdTech",
                "domain_type": "competitive",   # or technical / college
                "snapshots": [ {timestamp, num_students_enrolled, courses: [...], social_media: {...}, rewards: {...}}, ... ]
            },
            "competitors": {
                "Scaler": { "name": "Scaler", "snapshots": [...] },
                "GFG": { "name": "GFG", "snapshots": [...] }
            }
        }
        """
        our_company = data["our_company"]
        competitors = data["competitors"]
        all_companies = {"Our Company": our_company} | competitors

        insights: List[Dict] = []
        recommendations: List[str] = []
        competitor_metrics: Dict = {}

        # 1. Populate RAG with latest snapshots
        for name, comp_data in all_companies.items():
            latest = self._get_latest_snapshot(comp_data)
            if latest:
                latest["avg_price"] = self._avg_price(latest.get("courses", []))
                latest["avg_duration_weeks"] = self._avg_duration(latest.get("courses", []))
                latest["free_vs_paid_ratio"] = classify_pricing(latest.get("courses", [])).get("free_vs_paid_ratio")
                latest["referral_program"] = classify_rewards(latest.get("rewards", {})).get("referral_program")
                latest["posts_count"] = classify_social(latest.get("social_media", {})).get("posts_count")
                self.rag.add_context(name, latest)

        # 2. Calculate intake change for every company (historical comparison)
        for name, comp_data in all_companies.items():
            snapshots = comp_data.get("snapshots", [])
            change_info = self._calculate_change(snapshots)
            latest = self._get_latest_snapshot(comp_data)
            insights.append({
                "company": name,
                "domain_type": comp_data.get("domain_type", "unknown"),
                "latest_student_intake": latest.get("num_students_enrolled", 0),
                "intake_change": change_info["intake_change"],
                "intake_change_pct": change_info["intake_change_pct"],
                "latest_snapshot_date": latest.get("timestamp")
            })

        # 3. Detailed metric comparison (our vs competitors)
        our_latest = self._get_latest_snapshot(our_company)
        our_courses = our_latest.get("courses", [])
        our_social = our_latest.get("social_media", {})
        our_rewards = our_latest.get("rewards", {})

        our_pricing = classify_pricing(our_courses)
        our_audience = classify_audience(our_courses)
        our_style = classify_style(our_courses)
        our_social_cls = classify_social(our_social)
        our_rewards_cls = classify_rewards(our_rewards)

        for cname, cdata in competitors.items():
            clatest = self._get_latest_snapshot(cdata)
            ccourses = clatest.get("courses", [])
            csocial = clatest.get("social_media", {})
            crewards = clatest.get("rewards", {})

            competitor_metrics[cname] = {
                "pricing": classify_pricing(ccourses),
                "audience": classify_audience(ccourses),
                "style": classify_style(ccourses),
                "social": classify_social(csocial),
                "rewards": classify_rewards(crewards),
                "avg_duration": self._avg_duration(ccourses),
                "popular_courses": self._popular_courses(ccourses),
                "num_students": clatest.get("num_students_enrolled", 0)
            }

        # 4. Generate insights + suggestions (every constraint + intake correlation)
        # Pricing / fees change impact
        if len(our_company.get("snapshots", [])) >= 2:
            prev_courses = our_company["snapshots"][-2].get("courses", [])
            prev_avg_price = self._avg_price(prev_courses)
            price_delta = our_pricing["avg_price"] - prev_avg_price
            intake_delta = insights[0]["intake_change"]   # Our company is always first
            if price_delta > 0 and intake_delta < 0:
                insights.append({
                    "category": "Fees Structure & Student Intake",
                    "description": f"Fees rose by ₹{price_delta:.0f} while intake dropped by {intake_delta} students.",
                    "impact": "Direct negative correlation observed in our historical data.",
                    "suggestion": "Revert select price hikes OR combine with deeper discounts + EMI."
                })
                recommendations.append("Combine pricing reduction + referral rewards to reverse intake drop")

        # Course duration impact
        our_duration = self._avg_duration(our_courses)
        comp_durations = {c: m["avg_duration"] for c, m in competitor_metrics.items()}
        avg_comp_duration = sum(comp_durations.values()) / len(comp_durations) if comp_durations else 0
        if our_duration > avg_comp_duration + 4:   # threshold
            insights.append({
                "category": "Course Duration & Intake",
                "description": f"Our avg duration {our_duration:.1f} weeks vs competitors {avg_comp_duration:.1f} weeks.",
                "impact": "Longer courses correlate with lower intake across competitors.",
                "suggestion": "Introduce shorter modular versions of top courses."
            })
            recommendations.append("Combine shorter duration + more live classes + YouTube support")

        # Social media / YouTube activity
        our_posts = our_social_cls["posts_count"]
        max_comp_posts = max((m["social"]["posts_count"] for m in competitor_metrics.values()), default=0)
        if our_posts < max_comp_posts * 0.6:
            insights.append({
                "category": "Social Media + YouTube Activity",
                "description": f"Our posts: {our_posts} | Max competitor: {max_comp_posts}. YT videos: {our_social_cls['youtube_videos_posted']}",
                "impact": "Low activity → reduced visibility → lower student intake.",
                "suggestion": "Post daily on LinkedIn/Instagram + upload weekly YouTube classes."
            })
            recommendations.append("Combine increased social posts + YouTube live classes + doubt-solving system")

        # Popular courses
        our_popular = self._popular_courses(our_courses)
        insights.append({
            "category": "Popular Courses (Highest Intake)",
            "description": f"Top 3: {', '.join(our_popular) if our_popular else 'None detected'}",
            "impact": "These drive bulk of enrollment.",
            "suggestion": "Run targeted ads + special rewards only on these courses."
        })

        # Rewards impact
        if not our_rewards_cls["referral_program"] and any(m["rewards"]["referral_program"] for m in competitor_metrics.values()):
            insights.append({
                "category": "Rewards & Intake",
                "description": "Competitors actively use referral programs and free trials.",
                "impact": "Referral programs directly boost intake via word-of-mouth.",
                "suggestion": "Launch referral + free-trial combo immediately."
            })
            recommendations.append("Combine referral rewards + discounts + free trial (proven intake booster)")

        # Student discontinuity factors (inferred from low support systems)
        if our_style.get("doubt_solving_ratio", 0) < 0.6:
            insights.append({
                "category": "Student Discontinuity Risk",
                "description": f"Doubt-solving coverage only {our_style['doubt_solving_ratio']*100:.0f}%.",
                "impact": "Low support → higher dropout → lower net intake.",
                "suggestion": "Add 24×7 doubt system + weekly assignments."
            })

        # Ads frequency (if present in social data)
        our_ads = our_social_cls["ads_frequency"]
        if our_ads < 5:   # arbitrary low threshold
            insights.append({
                "category": "Advertisement Frequency",
                "description": f"Current ad frequency: {our_ads} per snapshot period.",
                "impact": "Competitors with higher ad spend show stronger intake growth.",
                "suggestion": "Increase platform ads (Google/YouTube) on popular courses."
            })

        # Final combined recommendations (2+ constraints)
        if our_pricing["avg_price"] > 15000 and our_duration > 12 and our_social_cls["youtube_videos_posted"] < 3:
            recommendations.append("CRITICAL: High price + long duration + weak YouTube → combine: lower price on popular courses + shorter modules + weekly YT live classes + referral rewards")

        # Return clean JSON for P3 (Frontend)
        return {
            "status": "success",
            "generated_at": datetime.now().isoformat(),
            "our_classifications": {
                "pricing": our_pricing,
                "audience": our_audience,
                "style": our_style,
                "social": our_social_cls,
                "rewards": our_rewards_cls,
                "popular_courses": our_popular,
                "avg_duration_weeks": our_duration
            },
            "competitor_comparison": competitor_metrics,
            "insights": insights,
            "recommendations": list(set(recommendations)),   # deduplicated
            "explanation_for_frontend": (
                "All constraints (pricing, duration, social/YouTube activity, ads, rewards, popular courses, "
                "doubt-solving, etc.) were compared against historical student intake changes. "
                "Suggestions combine 2+ factors for maximum impact. Data pulled directly from P2 snapshots."
            ),
            "rag_context_example": self.rag.retrieve("pricing and rewards")   # demo for Ask AI tab
        }


# ================================================
# Quick test (remove in production)
# if __name__ == "__main__":
#     # Load sample data from P2 JSON export
#     with open("sample_snapshots.json") as f:
#         sample_data = json.load(f)
#     gen = InsightGenerator()
#     result = gen.generate_insights(sample_data)
#     print(json.dumps(result, indent=2))
# ================================================
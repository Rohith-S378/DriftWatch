"""
insight_gen.py — P4 AI Insight Generator
Uses the Anthropic API to generate structured insights + recommendations
from the RAG context built over analyzer output.
"""

from __future__ import annotations
import os
import json
import requests
from dataclasses import dataclass, field

from analyzer import CompanyProfile, EdTechAnalyzer
from rag import RAGContextBuilder


# ──────────────────────────────────────────────
# Output Structures
# ──────────────────────────────────────────────

@dataclass
class Insight:
    category: str          # pricing | course | engagement | retention | combined
    severity: str          # critical | high | medium | low
    title: str
    explanation: str
    competitors_involved: list[str]
    intake_impact_estimate: str   # e.g. "+8–12% student intake"

@dataclass
class Recommendation:
    priority: int          # 1 = highest
    action: str
    rationale: str
    combined_constraints: list[str]   # which constraints this touches
    expected_intake_change: str
    effort: str           # low | medium | high
    timeline: str         # e.g. "2–4 weeks"

@dataclass
class InsightReport:
    company_name: str
    domain: str
    overall_score: float
    industry_avg_score: float
    student_intake_delta: float
    insights: list[Insight] = field(default_factory=list)
    recommendations: list[Recommendation] = field(default_factory=list)
    executive_summary: str = ""
    raw_context: str = ""


# ──────────────────────────────────────────────
# Insight Generator
# ──────────────────────────────────────────────

SYSTEM_PROMPT = """You are an elite EdTech competitive intelligence analyst.
You receive a structured comparison of one client EdTech company against its competitors,
covering: pricing, course structure, engagement (ads/social/YouTube), and retention (rewards/referrals/UX).

Your job is to return a JSON object (and ONLY valid JSON, no markdown fences) with this exact shape:

{
  "executive_summary": "<2–3 sentence board-level summary>",
  "insights": [
    {
      "category": "pricing|course|engagement|retention|combined",
      "severity": "critical|high|medium|low",
      "title": "<short title>",
      "explanation": "<detailed explanation referencing specific numbers from context, 2–4 sentences>",
      "competitors_involved": ["<name>"],
      "intake_impact_estimate": "<e.g. +8-12% student intake>"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "<concrete actionable step>",
      "rationale": "<why this will work, referencing competitor data>",
      "combined_constraints": ["pricing", "course"],
      "expected_intake_change": "<e.g. +10-15%>",
      "effort": "low|medium|high",
      "timeline": "<e.g. 2-4 weeks>"
    }
  ]
}

Rules:
- Generate 4–8 insights ordered by severity.
- Generate 5–8 recommendations ordered by priority (1 = most impactful).
- At least 3 recommendations MUST combine 2 or more constraints (e.g. pricing + course, engagement + retention).
- Reference actual numbers from the context (scores, percentages, counts).
- Insights should explain the "why" — how does this constraint change student intake?
- Be specific to the domain: competitive_exam | technical | college_school.
- Never hallucinate data not present in the context.
"""


class InsightGenerator:

    MODEL = "claude-sonnet-4-20250514"
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self):
        self.analyzer = EdTechAnalyzer()
        self.rag = RAGContextBuilder()

    def generate(
        self,
        client_snapshot: dict,
        competitor_snapshots: list[dict],
    ) -> InsightReport:
        # 1. Analyze
        client_profile = self.analyzer.analyze(client_snapshot)
        comp_profiles = self.analyzer.analyze_batch(competitor_snapshots)

        # 2. Build RAG context
        context = self.rag.build(client_profile, comp_profiles)

        # 3. Industry avg
        industry_avg = (
            sum(c.overall_score for c in comp_profiles) / len(comp_profiles)
            if comp_profiles else 0
        )

        # 4. Call Claude
        raw_json = self._call_llm(context, client_profile.domain)

        # 5. Parse
        report = InsightReport(
            company_name=client_profile.name,
            domain=client_profile.domain,
            overall_score=client_profile.overall_score,
            industry_avg_score=industry_avg,
            student_intake_delta=client_profile.student_intake_change_pct,
            raw_context=context,
        )

        try:
            parsed = json.loads(raw_json)
            report.executive_summary = parsed.get("executive_summary", "")
            report.insights = [
                Insight(**i) for i in parsed.get("insights", [])
            ]
            report.recommendations = [
                Recommendation(**r) for r in parsed.get("recommendations", [])
            ]
        except Exception as e:
            report.executive_summary = f"Parse error: {e}\nRaw: {raw_json[:500]}"

        return report

    def _call_llm(self, context: str, domain: str) -> str:
        user_msg = (
            f"Domain focus: {domain}\n\n"
            f"Competitive Intelligence Context:\n{context}\n\n"
            "Generate the JSON insight report now."
        )
        headers = {"Content-Type": "application/json","anthropic-version": "2023-06-01","x-api-key": os.environ.get("GEMINI_API_KEY", ""),}
        payload = {
            "model": self.MODEL,
            "max_tokens": 4096,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_msg}],
        }
        resp = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        return "".join(
            block.get("text", "")
            for block in data.get("content", [])
            if block.get("type") == "text"
        )

    # ── Serialisation for P3 ──────────────────────────────

    def report_to_dict(self, report: InsightReport) -> dict:
        """Convert InsightReport to a JSON-serialisable dict for P3's API."""
        from dataclasses import asdict
        return asdict(report)


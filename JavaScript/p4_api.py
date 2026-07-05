"""
p4_api.py — P4 FastAPI Service
Receives data from P2, runs the full P4 pipeline (analyzer → RAG → LLM),
and exposes clean JSON endpoints consumed by P3's dashboard.

Run with:
    uvicorn p4_api:app --reload --port 8001
"""

from __future__ import annotations
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any

from insight_gen import InsightGenerator
from analyzer import EdTechAnalyzer

app = FastAPI(
    title="P4 EdTech Intelligence API",
    description="AI insight engine for EdTech competitor analysis",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

generator = InsightGenerator()
analyzer = EdTechAnalyzer()


# ──────────────────────────────────────────────
# Request / Response Models
# ──────────────────────────────────────────────

class AnalysisRequest(BaseModel):
    client: dict[str, Any]
    competitors: list[dict[str, Any]]

class ScoreOnlyRequest(BaseModel):
    snapshots: list[dict[str, Any]]


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "P4 AI Engine running", "version": "1.0.0"}


@app.post("/insights")
def get_insights(req: AnalysisRequest):
    """
    Primary endpoint — full pipeline.
    P2 posts client + competitor snapshots → P4 returns insight report → P3 renders it.
    """
    try:
        report = generator.generate(req.client, req.competitors)
        return generator.report_to_dict(report)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/scores")
def get_scores(req: ScoreOnlyRequest):
    """
    Lightweight scoring only — no LLM call.
    Returns scored profiles for P3's overview charts.
    """
    try:
        profiles = analyzer.analyze_batch(req.snapshots)
        return [analyzer.to_dict(p) for p in profiles]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare")
def compare_two(req: AnalysisRequest):
    """
    Side-by-side comparison of client vs competitors with delta values.
    Used by P3's 'Changes' tab.
    """
    try:
        client = analyzer.analyze(req.client)
        comps = analyzer.analyze_batch(req.competitors)

        def delta(a, b):
            return round(b - a, 2)

        result = {
            "client": analyzer.to_dict(client),
            "competitors": [],
        }
        for comp in comps:
            result["competitors"].append({
                "profile": analyzer.to_dict(comp),
                "deltas": {
                    "overall_score": delta(client.overall_score, comp.overall_score),
                    "pricing_score": delta(client.pricing.score, comp.pricing.score),
                    "course_score": delta(client.courses.score, comp.courses.score),
                    "engagement_score": delta(client.engagement.score, comp.engagement.score),
                    "retention_score": delta(client.retention.score, comp.retention.score),
                    "student_intake_pct": delta(
                        client.student_intake_change_pct,
                        comp.student_intake_change_pct
                    ),
                },
            })
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


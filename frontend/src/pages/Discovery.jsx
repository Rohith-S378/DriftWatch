// frontend/src/pages/Discovery.jsx
// Prompt.txt Section 6 Page C compliant Competitor Discovery Page

import { useState, useEffect } from "react";
import AppLayout from "../components/AppLayout";
import {
  analyzeAndDiscover,
  listDiscoveryRuns,
  trackDiscoveryCandidate,
  dismissDiscoveryCandidate,
} from "../api.js";

export default function Discovery({ pythonOk }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [error, setError] = useState(null);
  const [successMsg, setSuccessMsg] = useState(null);
  const [currentRun, setCurrentRun] = useState(null);
  const [pastRuns, setPastRuns] = useState([]);
  const [trackingId, setTrackingId] = useState(null);

  useEffect(() => {
    loadPastRuns();
  }, []);

  async function loadPastRuns() {
    try {
      const runs = await listDiscoveryRuns();
      if (Array.isArray(runs)) {
        setPastRuns(runs);
        if (runs.length > 0 && !currentRun) {
          // Pre-populate latest run if available
          setCurrentRun(runs[0]);
        }
      }
    } catch (err) {
      console.error("Failed to load discovery history:", err);
    }
  }

  async function handleAnalyze(e) {
    if (e) e.preventDefault();
    if (!url.trim()) {
      setError("Please enter your company website URL.");
      return;
    }

    setLoading(true);
    setError(null);
    setSuccessMsg(null);
    setStatusMessage("Crawling company website and building business profile...");

    try {
      setTimeout(() => {
        setStatusMessage("Discovering competitor candidates via search provider...");
      }, 1500);

      setTimeout(() => {
        setStatusMessage("Verifying candidate landing pages and scoring match signals...");
      }, 3000);

      const result = await analyzeAndDiscover(url.trim());
      if (!result || result.error) {
        throw new Error(result?.error || "Failed to analyze website");
      }
      setCurrentRun(result);
      setStatusMessage("");
      loadPastRuns();
    } catch (err) {
      console.error("Discovery error:", err);
      setError(err.message || "Failed to analyze website and discover competitors.");
      setStatusMessage("");
    } finally {
      setLoading(false);
    }
  }

  async function handleTrack(candidate) {
    setTrackingId(candidate.id);
    setError(null);
    setSuccessMsg(null);
    try {
      const res = await trackDiscoveryCandidate(candidate.id, candidate.candidate_name);
      if (res.error) throw new Error(res.error);
      setSuccessMsg(`Successfully added "${candidate.candidate_name}" to active monitoring.`);
      setCurrentRun((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          candidates: prev.candidates.map((c) =>
            c.id === candidate.id ? { ...c, status: "tracked" } : c
          ),
        };
      });
    } catch (err) {
      setError(err.message || "Failed to track competitor.");
    } finally {
      setTrackingId(null);
    }
  }

  async function handleDismiss(candidate) {
    try {
      await dismissDiscoveryCandidate(candidate.id);
      setCurrentRun((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          candidates: prev.candidates.map((c) =>
            c.id === candidate.id ? { ...c, status: "dismissed" } : c
          ),
        };
      });
    } catch (err) {
      console.error("Failed to dismiss candidate:", err);
    }
  }

  return (
    <AppLayout pythonOk={pythonOk}>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Competitor Discovery
          </h1>
          <p className="text-xs text-slate-500 mt-1 max-w-2xl">
            Enter your company website. DriftWatch extracts your business profile,
            discovers direct and indirect competitors, verifies their websites,
            and presents explainable evidence-grounded recommendations.
          </p>
        </div>

        {/* Input Card */}
        <div className="dw-card p-6">
          <form onSubmit={handleAnalyze} className="space-y-4">
            <div>
              <label
                htmlFor="discoveryUrl"
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                Your company website
              </label>
              <div className="flex flex-col sm:flex-row gap-2">
                <input
                  id="discoveryUrl"
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://yourcompany.com"
                  disabled={loading}
                  required
                  className="dw-input flex-1"
                />
                <button
                  type="submit"
                  disabled={loading}
                  className="dw-btn dw-btn-primary px-6 text-xs font-semibold"
                >
                  {loading ? "Analyzing..." : "Discover Competitors"}
                </button>
              </div>
            </div>

            {loading && (
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md flex items-center gap-3 text-xs text-blue-800">
                <div className="w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                <span>{statusMessage}</span>
              </div>
            )}

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-xs text-red-700">
                {error}
              </div>
            )}

            {successMsg && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-md text-xs text-emerald-800">
                {successMsg}
              </div>
            )}
          </form>
        </div>

        {/* Structured Company Profile View (Prompt.txt Section 6 Page C) */}
        {currentRun && currentRun.company_profile && (
          <div className="dw-card p-6 border-l-4 border-l-blue-600 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-100 pb-3">
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded">
                  Company Profile
                </span>
                <h3 className="text-xl font-bold text-slate-900 mt-1">
                  {currentRun.company_name || currentRun.normalized_domain}
                </h3>
                <a
                  href={currentRun.target_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-slate-400 hover:text-blue-600"
                >
                  {currentRun.target_url}
                </a>
              </div>
              <div className="text-left sm:text-right">
                <div className="text-[10px] text-slate-400 uppercase font-semibold">
                  Profile Confidence
                </div>
                <div className="text-lg font-bold text-emerald-600">
                  {Math.round(
                    (currentRun.company_profile.confidence_score || 0.85) * 100
                  )}
                  %
                </div>
              </div>
            </div>

            <p className="text-xs text-slate-600 leading-relaxed">
              {currentRun.company_profile.company_description}
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
              <div className="p-3 bg-slate-50 rounded border border-slate-200 text-xs">
                <div className="text-[10px] font-semibold text-slate-400 uppercase">
                  Industry & Category
                </div>
                <div className="font-medium text-slate-800 mt-0.5">
                  {currentRun.company_profile.industry_category || "General"}
                </div>
              </div>
              <div className="p-3 bg-slate-50 rounded border border-slate-200 text-xs">
                <div className="text-[10px] font-semibold text-slate-400 uppercase">
                  Pricing Model
                </div>
                <div className="font-medium text-slate-800 mt-0.5">
                  {currentRun.company_profile.pricing_model || "Tiered / Contact Sales"}
                </div>
              </div>
              <div className="p-3 bg-slate-50 rounded border border-slate-200 text-xs">
                <div className="text-[10px] font-semibold text-slate-400 uppercase">
                  Target Audience
                </div>
                <div className="font-medium text-slate-800 mt-0.5">
                  {currentRun.company_profile.target_customers?.join(", ") ||
                    "Enterprises & Teams"}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Recommended Competitors Candidates */}
        {currentRun && currentRun.candidates && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">
                Recommended Competitors ({currentRun.candidates.length})
              </h3>
              <span className="text-xs text-slate-400">
                Ranked by multi-signal overlap
              </span>
            </div>

            {currentRun.candidates.length === 0 ? (
              <div className="dw-card p-8 text-center text-xs text-slate-500">
                No competitor candidates found for this domain.
              </div>
            ) : (
              <div className="space-y-3">
                {currentRun.candidates.map((cand) => (
                  <div
                    key={cand.id}
                    className={`dw-card p-5 space-y-3 transition-opacity ${
                      cand.status === "dismissed" ? "opacity-50" : ""
                    }`}
                  >
                    <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-bold text-slate-900">
                            {cand.candidate_name}
                          </h4>
                          <span
                            className={`dw-badge ${
                              cand.classification === "direct"
                                ? "dw-badge-high"
                                : cand.classification === "indirect"
                                ? "dw-badge-medium"
                                : "dw-badge-low"
                            }`}
                          >
                            {cand.classification}
                          </span>
                          {cand.is_verified && (
                            <span className="dw-badge dw-badge-success">
                              Verified
                            </span>
                          )}
                        </div>
                        <a
                          href={cand.website_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-[11px] text-slate-400 hover:text-blue-600 block mt-0.5"
                        >
                          {cand.website_url}
                        </a>
                      </div>

                      <div className="flex items-center gap-3 self-end sm:self-auto">
                        <div className="text-right">
                          <div className="text-[10px] text-slate-400 uppercase font-semibold">
                            Match Score
                          </div>
                          <div className="text-base font-bold text-blue-600">
                            {Math.round(cand.match_score)}/100
                          </div>
                        </div>

                        {cand.status === "tracked" ? (
                          <span className="dw-badge dw-badge-success py-1.5 px-3">
                            Monitored
                          </span>
                        ) : cand.status === "dismissed" ? (
                          <span className="dw-badge dw-badge-low py-1.5 px-3">
                            Dismissed
                          </span>
                        ) : (
                          <div className="flex gap-2">
                            <button
                              onClick={() => handleTrack(cand)}
                              disabled={trackingId === cand.id}
                              className="dw-btn dw-btn-primary px-3 py-1.5 text-xs font-medium"
                            >
                              {trackingId === cand.id ? "Tracking..." : "Track Competitor"}
                            </button>
                            <button
                              onClick={() => handleDismiss(cand)}
                              className="dw-btn dw-btn-secondary px-3 py-1.5 text-xs"
                            >
                              Dismiss
                            </button>
                          </div>
                        )}
                      </div>
                    </div>

                    <p className="text-xs text-slate-600 leading-relaxed">
                      {cand.match_explanation}
                    </p>

                    {/* Supporting Evidence Drawer */}
                    <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs space-y-1.5">
                      <div className="text-[11px] font-semibold text-slate-500">
                        Evidence & Snippet:
                      </div>
                      <p className="text-slate-600 italic text-[11px]">
                        "{cand.evidence?.search_snippet || "Discovered via industry search"}"
                      </p>
                      {cand.missing_evidence && cand.missing_evidence.length > 0 && (
                        <div className="text-[11px] text-amber-700">
                          <span className="font-semibold">Uncertainty / Missing Info: </span>
                          {cand.missing_evidence.join("; ")}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}

import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import {
  analyzeAndDiscover,
  listDiscoveryRuns,
  trackDiscoveryCandidate,
  dismissDiscoveryCandidate,
} from "../api.js";

function Discovery() {
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
    setCurrentRun(null);
    setStatusMessage("Crawling company website and building business profile...");

    try {
      setTimeout(() => {
        setStatusMessage("Discovering competitor candidates via search provider...");
      }, 1500);

      setTimeout(() => {
        setStatusMessage("Verifying candidate landing pages and scoring match signals...");
      }, 3000);

      const result = await analyzeAndDiscover(url.trim());
      console.log("Discovery API Result:", result);
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
      // Update local state status
      setCurrentRun((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          candidates: prev.candidates.map((c) =>
            c.id === candidate.id ? { ...c, status: "tracked" } : c
          ),
        };
      });
      if (window.refreshData) window.refreshData();
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
    <div className="p-8 max-w-6xl mx-auto">
      <Navbar />

      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Automated Competitor Discovery</h1>
        <p className="text-muted">
          Enter your company website. DriftWatch profiles your business, uncovers direct & indirect
          competitor candidates, verifies their offerings, and presents evidence-backed recommendations for monitoring.
        </p>
      </div>

      {/* Input Form */}
      <div className="glass-card p-6 mb-8">
        <form onSubmit={handleAnalyze} className="flex flex-col md:flex-row gap-4">
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://yourcompany.com"
            disabled={loading}
            className="flex-1 px-4 py-3 rounded bg-zinc-800 border border-zinc-700 text-white focus:outline-none focus:border-primary"
            required
          />
          <button
            type="submit"
            disabled={loading}
            className="btn btn-primary px-8 py-3 whitespace-nowrap font-medium"
          >
            {loading ? "Analyzing..." : "Discover Competitors"}
          </button>
        </form>

        {loading && (
          <div className="mt-4 p-4 rounded bg-zinc-900 border border-zinc-800 flex items-center gap-3">
            <div className="animate-spin h-5 w-5 border-2 border-primary border-t-transparent rounded-full"></div>
            <span className="text-sm text-zinc-300">{statusMessage}</span>
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 rounded bg-red-900/40 border border-red-700 text-red-200 text-sm">
            Error: {error}
          </div>
        )}

        {successMsg && (
          <div className="mt-4 p-4 rounded bg-green-900/40 border border-green-700 text-green-200 text-sm">
            Success: {successMsg}
          </div>
        )}
      </div>

      {/* Structured Company Profile View */}
      {currentRun && currentRun.company_profile && (
        <div className="glass-card p-6 mb-8 border-l-4 border-l-primary">
          <div className="flex justify-between items-start mb-4">
            <div>
              <span className="text-xs font-semibold px-2 py-1 rounded bg-zinc-800 text-primary uppercase tracking-wide">
                Generated Profile
              </span>
              <h2 className="text-2xl font-bold mt-1">{currentRun.company_name}</h2>
              <a
                href={currentRun.target_url}
                target="_blank"
                rel="noreferrer"
                className="text-xs text-muted hover:underline"
              >
                {currentRun.target_url}
              </a>
            </div>
            <div className="text-right">
              <span className="text-xs text-muted block">Profile Confidence</span>
              <span className="text-lg font-bold text-green-400">
                {Math.round((currentRun.company_profile.confidence_score || 0.8) * 100)}%
              </span>
            </div>
          </div>

          <p className="text-sm text-zinc-300 mb-4">{currentRun.company_profile.company_description}</p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs">
            <div className="p-3 rounded bg-zinc-900/60 border border-zinc-800">
              <span className="font-semibold text-zinc-400 block mb-1">Industry & Market</span>
              <p className="text-zinc-200">{currentRun.company_profile.industry_category}</p>
            </div>
            <div className="p-3 rounded bg-zinc-900/60 border border-zinc-800">
              <span className="font-semibold text-zinc-400 block mb-1">Pricing Model</span>
              <p className="text-zinc-200">{currentRun.company_profile.pricing_model || "Contact Sales"}</p>
            </div>
            <div className="p-3 rounded bg-zinc-900/60 border border-zinc-800">
              <span className="font-semibold text-zinc-400 block mb-1">Target Audience</span>
              <p className="text-zinc-200">
                {currentRun.company_profile.target_customers?.join(", ") || "General Market"}
              </p>
            </div>
          </div>

          {currentRun.company_profile.keywords && (
            <div className="mt-4 flex flex-wrap gap-1.5 items-center">
              <span className="text-xs text-zinc-400 mr-2">Key Topics:</span>
              {currentRun.company_profile.keywords.map((kw, i) => (
                <span key={i} className="px-2 py-0.5 rounded text-xs bg-zinc-800 text-zinc-300">
                  {kw}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Discovered Candidates List */}
      {currentRun && currentRun.candidates && (
        <div className="mb-12">
          <div className="flex justify-between items-center mb-4">
            <h3 className="text-xl font-bold">
              Ranked Competitor Recommendations ({currentRun.candidates.length})
            </h3>
            <span className="text-xs text-muted">Ranked by explainable multi-signal overlap</span>
          </div>

          {currentRun.candidates.length === 0 ? (
            <div className="p-8 text-center glass-card text-muted">
              No competitor candidates found matching current search signals.
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {currentRun.candidates.map((cand) => (
                <div
                  key={cand.id}
                  className={`glass-card p-5 transition-all ${
                    cand.status === "dismissed" ? "opacity-40" : ""
                  }`}
                >
                  <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 mb-3">
                    <div>
                      <div className="flex items-center gap-2">
                        <h4 className="text-lg font-bold">{cand.candidate_name}</h4>
                        <span
                          className={`text-xs px-2 py-0.5 rounded font-medium uppercase ${
                            cand.classification === "direct"
                              ? "bg-red-900/60 text-red-200 border border-red-700"
                              : cand.classification === "indirect"
                              ? "bg-amber-900/60 text-amber-200 border border-amber-700"
                              : "bg-blue-900/60 text-blue-200 border border-blue-700"
                          }`}
                        >
                          {cand.classification}
                        </span>
                        {cand.is_verified && (
                          <span className="text-xs px-2 py-0.5 rounded bg-green-900/40 text-green-300 border border-green-800">
                            Verified Site
                          </span>
                        )}
                      </div>
                      <a
                        href={cand.website_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-muted hover:underline"
                      >
                        {cand.website_url}
                      </a>
                    </div>

                    <div className="flex items-center gap-3">
                      <div className="text-right mr-2">
                        <span className="text-xs text-muted block">Match Score</span>
                        <span className="text-lg font-bold text-primary">
                          {Math.round(cand.match_score)}/100
                        </span>
                      </div>

                      {cand.status === "tracked" ? (
                        <button
                          disabled
                          className="px-4 py-2 rounded bg-green-900/30 text-green-400 border border-green-800 text-xs font-medium"
                        >
                          Monitored
                        </button>
                      ) : cand.status === "dismissed" ? (
                        <button
                          disabled
                          className="px-4 py-2 rounded bg-zinc-800 text-zinc-500 text-xs font-medium"
                        >
                          Dismissed
                        </button>
                      ) : (
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleTrack(cand)}
                            disabled={trackingId === cand.id}
                            className="btn btn-primary px-4 py-2 text-xs font-semibold"
                          >
                            {trackingId === cand.id ? "Tracking..." : "Track Competitor"}
                          </button>
                          <button
                            onClick={() => handleDismiss(cand)}
                            className="px-3 py-2 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 text-xs"
                          >
                            Dismiss
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <p className="text-sm text-zinc-300 mb-3">{cand.match_explanation}</p>

                  {/* Supporting Evidence Drawer */}
                  <div className="p-3 rounded bg-zinc-900/70 border border-zinc-800/80 text-xs">
                    <span className="font-semibold text-zinc-400 block mb-1">
                      Evidence & Search Match:
                    </span>
                    <p className="text-zinc-300 italic mb-2">
                      "{cand.evidence?.search_snippet || "Discovered via industry search"}"
                    </p>
                    {cand.evidence?.shared_keywords && cand.evidence.shared_keywords.length > 0 && (
                      <div className="flex flex-wrap gap-1 items-center">
                        <span className="text-zinc-400 mr-1">Shared Focus:</span>
                        {cand.evidence.shared_keywords.map((kw, i) => (
                          <span
                            key={i}
                            className="px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-300"
                          >
                            {kw}
                          </span>
                        ))}
                      </div>
                    )}

                    {cand.missing_evidence && cand.missing_evidence.length > 0 && (
                      <div className="mt-2 text-amber-400/80">
                        <span className="font-medium">Uncertainty / Missing Info: </span>
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
  );
}

export default Discovery;

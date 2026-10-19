// frontend/src/pages/Overview.jsx
// Prompt.txt Section 6 Page A & B compliant Overview / Competitors Page

import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../components/AppLayout";
import {
  listCompetitors,
  addCompetitor,
  removeCompetitor,
  triggerCrawl,
  crawlSingle,
  getChangeHistory,
} from "../api.js";

export default function Overview({ pythonOk }) {
  const [company, setCompany] = useState("");
  const [url, setUrl] = useState("");
  const [competitors, setCompetitors] = useState({});
  const [loading, setLoading] = useState(false);
  const [crawlResult, setCrawlResult] = useState(null);
  const [error, setError] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]);
  const [liveLoading, setLiveLoading] = useState(false);
  const [searchFilter, setSearchFilter] = useState("");
  const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

  const navigate = useNavigate();
  const domain = localStorage.getItem("domain") || "General";

  async function loadCompetitors() {
    try {
      const data = await listCompetitors();
      setCompetitors(data || {});
    } catch (err) {
      console.error("Failed to load competitors:", err);
      setError("Failed to load competitors. Please try again.");
    }
  }

  async function fetchLiveEvents() {
    if (Object.keys(competitors).length === 0) {
      setLiveEvents([]);
      return;
    }
    setLiveLoading(true);
    try {
      const eventsMap = {};
      const promises = Object.entries(competitors).map(async ([name]) => {
        try {
          const data = await getChangeHistory(name);
          if (Array.isArray(data)) {
            eventsMap[name] = data.slice(0, 5);
          } else {
            eventsMap[name] = [];
          }
        } catch (err) {
          eventsMap[name] = [];
        }
      });
      await Promise.all(promises);

      const allEvents = [];
      Object.entries(eventsMap).forEach(([source, events]) => {
        events.forEach((ev) => {
          allEvents.push({ ...ev, source });
        });
      });
      allEvents.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      setLiveEvents(allEvents.slice(0, 20));
    } catch (err) {
      console.error("Error fetching live events:", err);
    } finally {
      setLiveLoading(false);
    }
  }

  useEffect(() => {
    loadCompetitors();
  }, []);

  useEffect(() => {
    fetchLiveEvents();
    const interval = setInterval(fetchLiveEvents, 15000);
    return () => clearInterval(interval);
  }, [competitors]);

  async function handleSubmit(e) {
    if (e) e.preventDefault();
    if (!company.trim() || !url.trim()) {
      setError("Please fill all required fields.");
      return;
    }

    setLoading(true);
    setError(null);

    const result = await addCompetitor(company.trim(), url.trim());
    if (result.error) {
      setError(result.error);
      setLoading(false);
      return;
    }

    const crawl = await crawlSingle(company.trim(), url.trim());
    setCrawlResult(crawl);
    await loadCompetitors();
    setLoading(false);
    setIsAddDialogOpen(false);
    setCompany("");
    setUrl("");
  }

  const handleQuickCrawl = async (name) => {
    setLoading(true);
    await triggerCrawl(name);
    await loadCompetitors();
    await fetchLiveEvents();
    setLoading(false);
  };

  const handleRemove = async (name) => {
    if (!confirm(`Are you sure you want to stop monitoring ${name}?`)) return;
    await removeCompetitor(name);
    await loadCompetitors();
    await fetchLiveEvents();
  };

  const competitorEntries = Object.entries(competitors).filter(([name, compUrl]) => {
    if (!searchFilter.trim()) return true;
    const q = searchFilter.toLowerCase();
    return name.toLowerCase().includes(q) || compUrl.toLowerCase().includes(q);
  });

  return (
    <AppLayout pythonOk={pythonOk}>
      <div className="space-y-6">
        {/* Header row with Primary Action */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-slate-900">
              Overview
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">
              Monitor your competitive landscape for sector:{" "}
              <span className="font-semibold text-slate-700">{domain}</span>
            </p>
          </div>
          <button
            onClick={() => setIsAddDialogOpen(true)}
            className="dw-btn dw-btn-primary self-start sm:self-auto text-xs font-semibold"
          >
            + Add Competitor
          </button>
        </div>

        {/* Compact Metrics Row (Prompt.txt Section 6 Page A) */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="dw-card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Tracked Competitors
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {Object.keys(competitors).length}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Active monitoring targets
            </div>
          </div>
          <div className="dw-card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Total Detected Changes
            </div>
            <div className="text-2xl font-bold text-blue-600 mt-1">
              {liveEvents.length}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Recorded in recent polling
            </div>
          </div>
          <div className="dw-card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              High Severity Alerts
            </div>
            <div className="text-2xl font-bold text-amber-600 mt-1">
              {
                liveEvents.filter(
                  (e) => e.severity === "high" || e.severity === "critical"
                ).length
              }
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Requiring review
            </div>
          </div>
        </div>

        {/* Add Competitor Modal / Dialog */}
        {isAddDialogOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
            <div className="bg-white rounded-lg shadow-xl border border-slate-200 max-w-md w-full p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-sm font-semibold text-slate-900">
                  Add Competitor to Monitoring
                </h3>
                <button
                  onClick={() => setIsAddDialogOpen(false)}
                  className="text-slate-400 hover:text-slate-600 text-sm"
                >
                  ✕
                </button>
              </div>

              {error && (
                <div className="mb-4 p-2.5 bg-red-50 border border-red-200 rounded text-xs text-red-700">
                  {error}
                </div>
              )}

              <form onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Company Name
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Acme Corp"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    className="dw-input"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 mb-1">
                    Website or Pricing URL
                  </label>
                  <input
                    type="url"
                    required
                    placeholder="https://acme.com/pricing"
                    value={url}
                    onChange={(e) => setUrl(e.target.value)}
                    className="dw-input"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setIsAddDialogOpen(false)}
                    className="dw-btn dw-btn-secondary text-xs"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={loading}
                    className="dw-btn dw-btn-primary text-xs"
                  >
                    {loading ? "Adding & Crawling..." : "Add & Crawl Now"}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* Competitor Crawl Feedback Banner */}
        {crawlResult && crawlResult.success && (
          <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-md flex items-start gap-3">
            <span className="text-emerald-600 text-lg">✓</span>
            <div className="text-xs text-emerald-800">
              <div className="font-semibold">Crawl Completed Successfully</div>
              <p className="mt-0.5">
                Headline: <b>{crawlResult.headline || "N/A"}</b> · Pricing plans
                found: {crawlResult.pricing?.length || 0}
              </p>
            </div>
          </div>
        )}

        {crawlResult && !crawlResult.success && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-md flex items-start gap-3">
            <span className="text-red-600 text-lg">⚠</span>
            <div className="text-xs text-red-800">
              <div className="font-semibold">Crawl Failed</div>
              <p className="mt-0.5">{crawlResult.error || "Could not fetch competitor site."}</p>
            </div>
          </div>
        )}

        {/* Two-Column Main Content: Competitors Table & Live Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Competitors List (2 cols on large screens) */}
          <div className="lg:col-span-2 dw-card p-5 space-y-4">
            <div className="flex items-center justify-between gap-4">
              <h3 className="text-sm font-semibold text-slate-900">
                Tracked Competitors ({competitorEntries.length})
              </h3>
              <input
                type="text"
                placeholder="Search competitors..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="dw-input max-w-xs text-xs py-1.5"
              />
            </div>

            {competitorEntries.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500">
                No competitors found. Use the "+ Add Competitor" button or{" "}
                <button
                  onClick={() => navigate("/discovery")}
                  className="text-blue-600 underline font-medium"
                >
                  Discover Competitors
                </button>{" "}
                to start.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-slate-200 text-slate-400 font-semibold uppercase text-[10px]">
                      <th className="py-2.5 px-3">Company</th>
                      <th className="py-2.5 px-3">Status</th>
                      <th className="py-2.5 px-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {competitorEntries.map(([name, compUrl]) => (
                      <tr key={name} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3 px-3">
                          <div className="font-semibold text-slate-800">{name}</div>
                          <a
                            href={compUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="text-slate-400 hover:text-blue-600 truncate max-w-xs block text-[11px]"
                          >
                            {compUrl}
                          </a>
                        </td>
                        <td className="py-3 px-3">
                          <span className="dw-badge dw-badge-success">Active</span>
                        </td>
                        <td className="py-3 px-3 text-right space-x-2">
                          <button
                            onClick={() => handleQuickCrawl(name)}
                            disabled={loading}
                            className="dw-btn dw-btn-secondary px-2.5 py-1 text-xs"
                          >
                            Crawl Now
                          </button>
                          <button
                            onClick={() => handleRemove(name)}
                            className="dw-btn dw-btn-danger px-2.5 py-1 text-xs"
                          >
                            Remove
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Recent Changes Panel (1 col) */}
          <div className="dw-card p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-900">
                Recent Changes
              </h3>
              <button
                onClick={() => navigate("/changes")}
                className="text-xs text-blue-600 hover:underline font-medium"
              >
                View all →
              </button>
            </div>

            {liveLoading && liveEvents.length === 0 ? (
              <p className="text-xs text-slate-400 py-6 text-center">
                Checking for recent activity...
              </p>
            ) : liveEvents.length === 0 ? (
              <p className="text-xs text-slate-400 py-6 text-center">
                No recent changes detected across monitored competitors.
              </p>
            ) : (
              <div className="space-y-3">
                {liveEvents.slice(0, 6).map((ev, idx) => (
                  <div
                    key={ev.id || idx}
                    className="p-3 rounded-md border border-slate-200 bg-slate-50/50 space-y-1.5"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-800">
                        {ev.source || ev.source_id}
                      </span>
                      <span
                        className={`dw-badge ${
                          ev.severity === "critical"
                            ? "dw-badge-critical"
                            : ev.severity === "high"
                            ? "dw-badge-high"
                            : ev.severity === "medium"
                            ? "dw-badge-medium"
                            : "dw-badge-low"
                        }`}
                      >
                        {ev.severity || "Low"}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 line-clamp-2">
                      {ev.description}
                    </p>
                    <div className="text-[10px] text-slate-400">
                      {ev.created_at ? new Date(ev.created_at).toLocaleTimeString() : "Recent"}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

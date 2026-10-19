// frontend/src/pages/Changes.jsx
// Prompt.txt Section 6 Page D compliant Changes Page

import { useState, useMemo } from "react";
import AppLayout from "../components/AppLayout";

export default function Changes({ events = [], sources = [], pythonOk }) {
  const [filterValue, setFilterValue] = useState("all");
  const [sortValue, setSortValue] = useState("date_desc");
  const [searchQuery, setSearchQuery] = useState("");
  const [showTechnicalUpdates, setShowTechnicalUpdates] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});
  const [selectedChange, setSelectedChange] = useState(null);

  const toggleGroup = (key) => {
    setExpandedGroups((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const getSeverityBadgeClass = (severity) => {
    switch (severity) {
      case "critical":
        return "dw-badge-critical";
      case "high":
        return "dw-badge-high";
      case "medium":
        return "dw-badge-medium";
      default:
        return "dw-badge-low";
    }
  };

  const isTechnicalChange = (event) => {
    if (event.change_type !== "messaging") return false;
    if (!event.diff) return false;
    return false;
  };

  const filteredEvents = useMemo(() => {
    let filtered = events;

    if (!showTechnicalUpdates) {
      filtered = filtered.filter((event) => !isTechnicalChange(event));
    }

    if (filterValue !== "all") {
      if (filterValue === "critical") {
        filtered = filtered.filter((e) => e.severity === "critical");
      } else if (filterValue === "high") {
        filtered = filtered.filter(
          (e) => e.severity === "high" || e.severity === "critical"
        );
      } else {
        filtered = filtered.filter((e) => e.change_type === filterValue);
      }
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (e) =>
          (e.description && e.description.toLowerCase().includes(q)) ||
          (e.source_id && e.source_id.toLowerCase().includes(q)) ||
          (e.change_type && e.change_type.toLowerCase().includes(q))
      );
    }

    return filtered;
  }, [events, filterValue, showTechnicalUpdates, searchQuery]);

  const sortedEvents = useMemo(() => {
    const sorted = [...filteredEvents];
    switch (sortValue) {
      case "date_asc":
        sorted.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        break;
      case "date_desc":
        sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        break;
      case "severity": {
        const severityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
        sorted.sort(
          (a, b) =>
            (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0)
        );
        break;
      }
      default:
        sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }
    return sorted;
  }, [filteredEvents, sortValue]);

  return (
    <AppLayout pythonOk={pythonOk}>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Competitor Changes
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Track and inspect detected changes across your monitored competitors.
          </p>
        </div>

        {/* Filter and Search Bar (Prompt.txt Section 6 Page D) */}
        <div className="dw-card p-4 space-y-3">
          <div className="flex flex-col md:flex-row gap-3">
            <input
              type="text"
              placeholder="Search changes by description, competitor, or type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="dw-input flex-1 text-xs"
            />
            <div className="flex gap-2">
              <select
                value={filterValue}
                onChange={(e) => setFilterValue(e.target.value)}
                className="dw-input text-xs w-44"
              >
                <option value="all">All Changes</option>
                <option value="critical">Critical Only</option>
                <option value="high">High & Critical</option>
                <option value="price">Pricing Changes</option>
                <option value="keyword">Keyword/SEO</option>
                <option value="messaging">Messaging</option>
                <option value="anomaly">Unusual</option>
              </select>
              <select
                value={sortValue}
                onChange={(e) => setSortValue(e.target.value)}
                className="dw-input text-xs w-36"
              >
                <option value="date_desc">Newest First</option>
                <option value="date_asc">Oldest First</option>
                <option value="severity">By Priority</option>
              </select>
            </div>
          </div>
        </div>

        {/* Changes Feed */}
        {sortedEvents.length === 0 ? (
          <div className="dw-card p-12 text-center text-xs text-slate-500">
            No changes detected matching your filter criteria.
          </div>
        ) : (
          <div className="space-y-3">
            {sortedEvents.map((event) => (
              <div
                key={event.id}
                className="dw-card p-4 hover:border-slate-300 transition-colors space-y-2.5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span
                      className={`dw-badge ${getSeverityBadgeClass(
                        event.severity
                      )}`}
                    >
                      {event.severity ? event.severity.toUpperCase() : "LOW"}
                    </span>
                    <span className="text-xs font-semibold text-slate-800 uppercase tracking-wider">
                      {event.change_type}
                    </span>
                    <span className="text-slate-300">·</span>
                    <span className="text-xs font-bold text-blue-600">
                      {event.source_id || "Competitor"}
                    </span>
                  </div>
                  <div className="text-[11px] text-slate-400">
                    {event.created_at
                      ? new Date(event.created_at).toLocaleString()
                      : "Recent"}
                  </div>
                </div>

                <p className="text-xs text-slate-700 leading-relaxed font-medium">
                  {event.description}
                </p>

                {(event.old_value || event.new_value) && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs pt-1">
                    {event.old_value && (
                      <div className="p-2 rounded bg-red-50 border border-red-100 text-red-800">
                        <span className="font-semibold block text-[10px] uppercase text-red-600">
                          Previous
                        </span>
                        <div className="truncate">{String(event.old_value)}</div>
                      </div>
                    )}
                    {event.new_value && (
                      <div className="p-2 rounded bg-emerald-50 border border-emerald-100 text-emerald-800">
                        <span className="font-semibold block text-[10px] uppercase text-emerald-600">
                          New Value
                        </span>
                        <div className="truncate">{String(event.new_value)}</div>
                      </div>
                    )}
                  </div>
                )}

                <div className="flex justify-end pt-1">
                  <button
                    onClick={() => setSelectedChange(event)}
                    className="dw-btn dw-btn-secondary px-2.5 py-1 text-xs"
                  >
                    View Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Change Detail Dialog / Modal (Prompt.txt Section 6 Page D) */}
        {selectedChange && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/40 p-4">
            <div className="bg-white rounded-lg shadow-xl border border-slate-200 max-w-lg w-full p-6 space-y-4">
              <div className="flex justify-between items-start">
                <div>
                  <span
                    className={`dw-badge ${getSeverityBadgeClass(
                      selectedChange.severity
                    )}`}
                  >
                    {selectedChange.severity?.toUpperCase()}
                  </span>
                  <h3 className="text-sm font-bold text-slate-900 mt-1">
                    {selectedChange.source_id} — {selectedChange.change_type}
                  </h3>
                </div>
                <button
                  onClick={() => setSelectedChange(null)}
                  className="text-slate-400 hover:text-slate-600 text-sm"
                >
                  ✕
                </button>
              </div>

              <div className="text-xs text-slate-500">
                Detected:{" "}
                <span className="font-medium text-slate-700">
                  {selectedChange.created_at
                    ? new Date(selectedChange.created_at).toLocaleString()
                    : "Recent"}
                </span>
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded text-xs text-slate-700 leading-relaxed">
                {selectedChange.description}
              </div>

              {selectedChange.diff && (
                <div>
                  <div className="text-[11px] font-semibold text-slate-400 uppercase mb-1">
                    Raw Diff Structure
                  </div>
                  <pre className="p-3 bg-slate-900 text-slate-100 rounded text-[11px] font-mono overflow-x-auto max-h-48">
                    {JSON.stringify(selectedChange.diff, null, 2)}
                  </pre>
                </div>
              )}

              <div className="flex justify-end pt-2">
                <button
                  onClick={() => setSelectedChange(null)}
                  className="dw-btn dw-btn-secondary text-xs"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppLayout>
  );
}

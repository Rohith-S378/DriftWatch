import Navbar from "../components/Navbar";
import { useState, useMemo } from "react";

function Changes({ events, sources }) {
  // State for filtering and sorting
  const [filterValue, setFilterValue] = useState("all");
  const [sortValue, setSortValue] = useState("date_desc");
  const [showTechnicalUpdates, setShowTechnicalUpdates] = useState(false);
  const [expandedGroups, setExpandedGroups] = useState({});

  const toggleGroup = (key) => {
    setExpandedGroups(prev => ({ ...prev, [key]: !prev[key] }));
  };

  // Helper functions for business-friendly display
  const getChangeImpactDescription = (change_type, severity, description) => {
    const impactMap = {
      price: {
        critical: "Significant pricing change that may affect market positioning and profitability",
        high: "Notable pricing adjustment that could impact competitiveness",
        medium: "Moderate pricing update worth monitoring",
        low: "Minor pricing tweak with limited impact"
      },
      keyword: {
        critical: "Major SEO/content strategy shift that could dramatically affect visibility",
        high: "Important keyword strategy change affecting search rankings",
        medium: "Notable keyword adjustment worth tracking",
        low: "Minor keyword update"
      },
      messaging: {
        critical: "Fundamental brand messaging change that could alter market perception",
        high: "Significant messaging update affecting brand positioning",
        medium: "Notable messaging tweak worth reviewing",
        low: "Minor messaging adjustment"
      },
      anomaly: {
        critical: "Unusual market activity requiring immediate investigation",
        high: "Atypical competitor behavior worth close monitoring",
        medium: "Unusual activity worth noting",
        low: "Minor irregularity"
      }
    };

    return impactMap[change_type]?.[severity] || "Change detected requiring review";
  };

  const getBusinessImpactIcon = (change_type) => {
    const iconMap = {
      price: "💰",
      keyword: "🔍",
      messaging: "💬",
      anomaly: "⚠️"
    };
    return iconMap[change_type] || "📊";
  };

  // Severity → visual language, defined once so badge, dot, and left-border
  // all agree with each other and none of it depends on CSS cascade order
  // (using inline styles here so it can't be silently overridden by other
  // global utility classes like `.glass`).
  const severityStyles = {
    critical: { accent: "#dc2626", bg: "#fee2e2", text: "#991b1b", label: "Critical" },
    high:     { accent: "#ef4444", bg: "#fee2e2", text: "#b91c1c", label: "High" },
    medium:   { accent: "#f59e0b", bg: "#fef3c7", text: "#92400e", label: "Medium" },
    low:      { accent: "#9ca3af", bg: "#f3f4f6", text: "#4b5563", label: "Low" },
  };
  const getSeverityStyle = (severity) => severityStyles[severity] || severityStyles.low;

  // ── Technical / cosmetic change detection ──────────────────────────────
  const TECHNICAL_FIELD_NAMES = new Set([
    "scraped_at", "crawled_url", "crawl_time", "crawl_url", "fetch_time",
    "updated_at", "created_at", "timestamp", "version", "metadata",
    "index", "batch", "synced_at", "last_updated_at", "full_text"
  ]);

  const isTechnicalFieldName = (name) => {
    if (!name) return false;
    const lower = name.toLowerCase();
    if (TECHNICAL_FIELD_NAMES.has(lower)) return true;
    return /^(scraped|crawl|fetch|synced|metadata|batch|index)/i.test(lower) ||
           /(_at|_time|_version|timestamp)$/i.test(lower);
  };

  const isCosmeticValueChange = (oldVal, newVal) => {
    if (oldVal === undefined || newVal === undefined || oldVal === null || newVal === null) {
      return false;
    }
    const normalize = (s) =>
      String(s).trim().replace(/\/+$/, "").replace(/^https?:\/\//i, "");
    return normalize(oldVal) === normalize(newVal);
  };

  const extractLeafFieldName = (path) => {
    const matches = [...String(path).matchAll(/\['?([^'\]]+)'?\]/g)];
    return matches.length > 0 ? matches[matches.length - 1][1] : null;
  };

  const isTechnicalChange = (event) => {
    if (event.change_type !== "messaging") return false;
    if (!event.diff) return false;

    const diff = event.diff;
    let sawAnyChange = false;

    if (diff.values_changed) {
      for (const [path, detail] of Object.entries(diff.values_changed)) {
        sawAnyChange = true;
        const fieldName = extractLeafFieldName(path);
        const cosmetic = isCosmeticValueChange(detail?.old_value, detail?.new_value);
        if (!cosmetic && !isTechnicalFieldName(fieldName)) return false;
      }
    }
    if (diff.dictionary_item_added) {
      for (const path of Object.keys(diff.dictionary_item_added)) {
        sawAnyChange = true;
        if (!isTechnicalFieldName(extractLeafFieldName(path))) return false;
      }
    }
    if (diff.dictionary_item_removed) {
      for (const path of Object.keys(diff.dictionary_item_removed)) {
        sawAnyChange = true;
        if (!isTechnicalFieldName(extractLeafFieldName(path))) return false;
      }
    }
    if (diff.iterable_item_added) {
      for (const path of Object.keys(diff.iterable_item_added)) {
        sawAnyChange = true;
        if (!isTechnicalFieldName(extractLeafFieldName(path))) return false;
      }
    }
    if (diff.iterable_item_removed) {
      for (const path of Object.keys(diff.iterable_item_removed)) {
        sawAnyChange = true;
        if (!isTechnicalFieldName(extractLeafFieldName(path))) return false;
      }
    }

    return sawAnyChange;
  };

  // Format date for display — relative for recent items, absolute for older
  const formatDate = (dateString) => {
    if (!dateString) return "Unknown date";
    try {
      const date = new Date(dateString);
      const now = new Date();
      const diffMs = now - date;
      const diffMins = Math.floor(diffMs / 60000);
      const diffHours = Math.floor(diffMins / 60);
      const diffDays = Math.floor(diffHours / 24);

      if (diffMins < 1) return "Just now";
      if (diffMins < 60) return `${diffMins} min${diffMins === 1 ? "" : "s"} ago`;
      if (diffHours < 24) return `${diffHours} hour${diffHours === 1 ? "" : "s"} ago`;
      if (diffDays === 1) return "Yesterday";
      if (diffDays < 7) return `${diffDays} days ago`;

      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric"
      });
    } catch (e) {
      return "Invalid date";
    }
  };

  // Extract meaningful change details from diff if old_value/new_value not available
  const getChangeDetails = (event) => {
    if ((event.old_value !== null && event.old_value !== undefined) ||
        (event.new_value !== null && event.new_value !== undefined)) {
      return {
        oldValue: event.old_value !== null && event.old_value !== undefined ?
                  String(event.old_value) : null,
        newValue: event.new_value !== null && event.new_value !== undefined ?
                  String(event.new_value) : null
      };
    }

    if (!event.diff) return null;

    try {
      switch (event.change_type) {
        case "price":
          if (event.diff.plan && event.diff.old !== undefined && event.diff.new !== undefined) {
            return {
              oldValue: `Plan "${event.diff.plan}": ${event.diff.old}`,
              newValue: `Plan "${event.diff.plan}": ${event.diff.new}`
            };
          }
          break;
        case "keyword":
          if (event.diff.added && event.diff.added.length > 0) {
            return { oldValue: "None", newValue: `Added: ${event.diff.added.join(", ")}` };
          }
          if (event.diff.removed && event.diff.removed.length > 0) {
            return { oldValue: `Removed: ${event.diff.removed.join(", ")}`, newValue: "None" };
          }
          if (event.diff.discovered_in_text && event.diff.discovered_in_text.length > 0) {
            return {
              oldValue: "Not previously detected",
              newValue: `Detected in content: ${event.diff.discovered_in_text.join(", ")}`
            };
          }
          break;
        case "messaging":
          if (event.diff.values_changed) {
            const changes = Object.entries(event.diff.values_changed);
            if (changes.length > 0) {
              const [path, detail] = changes[0];
              const fieldName = path.replace(/['"]/g, "").replace(/^root\[/, "").replace(/\]$/, "");
              return {
                oldValue: `${fieldName}: "${detail.old_value}"`,
                newValue: `${fieldName}: "${detail.new_value}"`
              };
            }
          }
          if (event.diff.dictionary_item_added) {
            const count = Object.keys(event.diff.dictionary_item_added).length;
            return { oldValue: "Field not present", newValue: `${count} field(s) added` };
          }
          if (event.diff.dictionary_item_removed) {
            const count = Object.keys(event.diff.dictionary_item_removed).length;
            return { oldValue: `${count} field(s) removed`, newValue: "Field not present" };
          }
          break;
        case "anomaly":
          if (event.new_value !== null && event.new_value !== undefined) {
            return {
              oldValue: "Within normal range",
              newValue: `Price: ${event.new_value} (${event.description.split(":")[1]?.trim() || ""})`
            };
          }
          break;
        default:
          return { oldValue: "See details below", newValue: "See details below" };
      }
    } catch (e) {
      console.error("Error extracting change details:", e);
    }
    return null;
  };

  // Filter events based on selected filter
  const filteredEvents = useMemo(() => {
    let filtered = events;

    if (!showTechnicalUpdates) {
      filtered = filtered.filter(event => !isTechnicalChange(event));
    }

    if (filterValue === "all") return filtered;
    if (filterValue === "critical") return filtered.filter(e => e.severity === "critical");
    if (filterValue === "high") return filtered.filter(e => e.severity === "high" || e.severity === "critical");

    return filtered.filter(e => e.change_type === filterValue);
  }, [events, filterValue, showTechnicalUpdates]);

  // Sort events based on selected sort option
  const sortedEvents = useMemo(() => {
    let sorted = [...filteredEvents];

    switch (sortValue) {
      case "date_asc":
        sorted.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        break;
      case "date_desc":
        sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        break;
      case "severity": {
        const severityOrder = { critical: 4, high: 3, medium: 2, low: 1 };
        sorted.sort((a, b) => (severityOrder[b.severity] || 0) - (severityOrder[a.severity] || 0));
        break;
      }
      case "type":
        sorted.sort((a, b) => a.change_type.localeCompare(b.change_type));
        break;
      default:
        sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    }

    return sorted;
  }, [filteredEvents, sortValue]);

  // ── Grouping ─────────────────────────────────────────────────────────
  // Collapse repeated low/medium-severity changes from the same source +
  // change type into a single card with a "+N similar updates" toggle.
  // Critical/high severity items are NEVER grouped, so nothing important
  // can end up hidden behind a click.
  const groupedItems = useMemo(() => {
    const groups = [];
    const groupMap = new Map();

    for (const event of sortedEvents) {
      const collapsible = event.severity === "low" || event.severity === "medium";
      const key = collapsible ? `${event.source_id || "unknown"}::${event.change_type}` : null;

      if (!collapsible) {
        groups.push({ type: "single", event, renderKey: event.id });
        continue;
      }

      if (groupMap.has(key)) {
        groupMap.get(key).items.push(event);
      } else {
        const entry = { type: "group", key, items: [event], renderKey: key };
        groupMap.set(key, entry);
        groups.push(entry);
      }
    }

    // A "group" of exactly one item is just a single card — no point
    // showing an expandable toggle for something with nothing to expand.
    return groups.map(g =>
      g.type === "group" && g.items.length === 1
        ? { type: "single", event: g.items[0], renderKey: g.items[0].id }
        : g
    );
  }, [sortedEvents]);

  const hiddenTechnicalCount = showTechnicalUpdates
    ? 0
    : events.filter(isTechnicalChange).length;

  // Renders a single change card. Shared by both standalone events and
  // items inside an expanded group, so they look identical either way.
  const renderEventCard = (event) => {
    const sevStyle = getSeverityStyle(event.severity);
    const changeDetails = getChangeDetails(event);

    return (
      <div
        key={event.id}
        className="glass p-5 mb-4"
        style={{ borderLeft: `4px solid ${sevStyle.accent}` }}
      >
        <div className="flex justify-between items-start mb-3">
          <div className="flex items-center space-x-3">
            <div className="text-2xl">{getBusinessImpactIcon(event.change_type)}</div>
            <div className="space-y-1">
              <h3 className="font-semibold text-lg">
                {event
                  .change_type
                  .split("_")
                  .map(w => w.charAt(0).toUpperCase() + w.slice(1))
                  .join(" ")}
              </h3>
              <div className="flex items-center space-x-2 text-xs text-muted">
                <p className="m-0">{formatDate(event.created_at)}</p>
                <p className="m-0">{event.source_id || "Unknown source"}</p>
              </div>
            </div>
          </div>
          <div
            className="text-xs px-3 py-1 rounded-full flex items-center gap-1.5 font-medium"
            style={{ backgroundColor: sevStyle.bg, color: sevStyle.text }}
          >
            <span
              className="inline-block w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: sevStyle.accent }}
            />
            {sevStyle.label}
          </div>
        </div>

        {/* Business impact line for high/critical */}
        {event.severity === "high" || event.severity === "critical" ? (
          <div className="mb-3">
            <p className="text-muted">{getChangeImpactDescription(event.change_type, event.severity, event.description)}</p>
          </div>
        ) : null}

        {/* Diff section directly */}
        <div className="space-y-2">
          {changeDetails ? (
            <>
              {changeDetails.oldValue !== null && (
                <div className="flex items-start space-x-3 p-3 bg-red-50 rounded-lg border-l-2 border-red-200">
                  <div className="flex-shrink-0 mt-1">➖</div>
                  <div>
                    <div className="font-medium text-sm text-red-800">Previous Value</div>
                    <div className="text-xs text-red-600 break-all">
                      {String(changeDetails.oldValue).substring(0, 100)}
                      {String(changeDetails.oldValue).length > 100 ? "..." : ""}
                    </div>
                  </div>
                </div>
              )}
              {changeDetails.newValue !== null && (
                <div className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg border-l-2 border-green-200">
                  <div className="flex-shrink-0 mt-1">➕</div>
                  <div>
                    <div className="font-medium text-sm text-green-800">New Value</div>
                    <div className="text-xs text-green-600 break-all">
                      {String(changeDetails.newValue).substring(0, 100)}
                      {String(changeDetails.newValue).length > 100 ? "..." : ""}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-sm text-center text-muted py-4 italic">
              No specific value changes detected (structural or metadata update)
            </div>
          )}
        </div>

        <div className="mt-4 pt-3 border-t border-gray-200">
          <div className="flex justify-between items-center text-xs">
            <span className="text-muted">Change ID: {event.id.substring(0, 8)}...</span>
            <button
              onClick={() => {
                alert("Action would be taken based on this change in a production system");
              }}
              className="input input-xs bg-blue-50 hover:bg-blue-100 text-blue-800 px-3 py-1 rounded"
            >
              Take Action
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div>
      <Navbar />
      <h2 className="text-2xl font-bold mb-6 text-gradient">Competitive Change Intelligence</h2>
      <p className="text-muted mb-6">
        Comprehensive view of competitor activities with actionable business insights
      </p>

      {events.length === 0 ? (
        <div className="glass-card p-8 text-center">
          <div className="space-y-4">
            <p className="text-xl text-muted">No competitor changes detected yet</p>
            <p className="text-muted">To start tracking competitive intelligence:</p>
            <ol className="list-decimal list-inside text-sm text-muted mt-2 space-y-1">
              <li>Add competitors using the "Add Competitor" feature</li>
              <li>Initiate crawls to begin monitoring</li>
              <li>Return here to view detected changes with business insights</li>
            </ol>
          </div>
        </div>
      ) : (
        <>
          {/* Summary Bar */}
          <div className="glass-card p-4 mb-6 flex flex-wrap gap-4">
            <div className="flex items-center space-x-3 p-3 bg-gradient-to-r from-indigo-600 to-violet-500 rounded-lg flex-1 min-w-[150px]">
              <div className="text-2xl font-bold text-white">{events.length}</div>
              <div>
                <div className="font-medium text-white">Total Changes</div>
                <div className="text-xs text-white/80">Tracked this period</div>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-3 bg-gradient-to-r from-indigo-600 to-violet-500 rounded-lg flex-1 min-w-[150px]">
              <div className="text-2xl font-bold text-white">{sources.length}</div>
              <div>
                <div className="font-medium text-white">Competitors Monitored</div>
                <div className="text-xs text-white/80">Active sources</div>
              </div>
            </div>
            <div className="flex items-center space-x-3 p-3 bg-gradient-to-r from-indigo-600 to-violet-500 rounded-lg flex-1 min-w-[150px]">
              <div className="text-2xl font-bold text-white">
                {events.filter(e => e.severity === "critical" || e.severity === "high").length}
              </div>
              <div>
                <div className="font-medium text-white">Priority Alerts</div>
                <div className="text-xs text-white/80">Requiring attention</div>
              </div>
            </div>
          </div>

          {/* Filter Controls */}
          <div className="glass-card p-4 mb-6 flex flex-wrap items-center gap-4">
            <div className="flex items-center space-x-2">
              <span className="font-medium">Filter by:</span>
              <select
                className="input ml-2 w-[200px]"
                value={filterValue}
                onChange={(e) => setFilterValue(e.target.value)}
              >
                <option value="all">All Changes</option>
                <option value="critical">Critical Only</option>
                <option value="high">High & Critical</option>
                <option value="price">Pricing Changes</option>
                <option value="keyword">Keyword/SEO</option>
                <option value="messaging">Messaging/Brand</option>
                <option value="anomaly">Unusual Activities</option>
              </select>
            </div>
            <div className="flex items-center space-x-2">
              <span className="font-medium">Sort by:</span>
              <select
                className="input ml-2 w-[200px]"
                value={sortValue}
                onChange={(e) => setSortValue(e.target.value)}
              >
                <option value="date_desc">Newest First</option>
                <option value="date_asc">Oldest First</option>
                <option value="severity">By Priority</option>
                <option value="type">By Change Type</option>
              </select>
            </div>
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                id="show-technical"
                checked={showTechnicalUpdates}
                onChange={(e) => setShowTechnicalUpdates(e.target.checked)}
                className="toggle toggle-primary"
              />
              <label htmlFor="show-technical" className="text-sm font-medium">
                Show technical updates
                {hiddenTechnicalCount > 0 && (
                  <span className="text-muted"> ({hiddenTechnicalCount} hidden)</span>
                )}
              </label>
            </div>
          </div>

          {/* Changes List */}
          <div className="space-y-2">
            {groupedItems.map((item) => {
              if (item.type === "single") {
                return renderEventCard(item.event);
              }

              // Grouped: show the first (most relevant, per current sort)
              // item expanded, with the rest tucked behind a toggle.
              const [primary, ...rest] = item.items;
              const isExpanded = !!expandedGroups[item.key];

              return (
                <div key={item.key}>
                  {renderEventCard(primary)}
                  <div className="pl-4 -mt-3 mb-4">
                    <button
                      onClick={() => toggleGroup(item.key)}
                      className="text-xs text-blue-700 hover:underline font-medium"
                    >
                      {isExpanded ? "▲ Hide" : "▼ Show"} {rest.length} similar update{rest.length === 1 ? "" : "s"} from {primary.source_id || "this source"}
                    </button>
                    {isExpanded && (
                      <div className="mt-3 space-y-3 border-l-2 border-gray-200 pl-3">
                        {rest.map((e) => renderEventCard(e))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

export default Changes;
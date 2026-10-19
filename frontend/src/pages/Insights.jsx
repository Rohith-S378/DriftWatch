// frontend/src/pages/Insights.jsx
// Prompt.txt Section 6 Page E compliant Insights Page

import AppLayout from "../components/AppLayout";

export default function Insights({ events = [], sources = [], pythonOk }) {
  // Aggregate real events for business intelligence
  const totalChanges = events.length;
  const criticalCount = events.filter((e) => e.severity === "critical").length;
  const highCount = events.filter((e) => e.severity === "high").length;
  const routineCount = events.filter(
    (e) => e.severity === "medium" || e.severity === "low"
  ).length;

  // Category counts
  const categories = {};
  events.forEach((e) => {
    const type = e.change_type || "other";
    categories[type] = (categories[type] || 0) + 1;
  });

  const categoryEntries = Object.entries(categories).sort(
    (a, b) => b[1] - a[1]
  );
  const maxCategoryCount = Math.max(...Object.values(categories), 1);

  return (
    <AppLayout pythonOk={pythonOk}>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Intelligence Insights
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Strategic breakdown of competitor movements, pricing shifts, and focus areas.
          </p>
        </div>

        {/* Executive Metric Cards (Prompt.txt Section 6 Page E) */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
          <div className="dw-card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Total Changes
            </div>
            <div className="text-2xl font-bold text-slate-900 mt-1">
              {totalChanges}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Detected across competitors
            </div>
          </div>
          <div className="dw-card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Critical Alerts
            </div>
            <div className="text-2xl font-bold text-red-600 mt-1">
              {criticalCount}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Requiring immediate attention
            </div>
          </div>
          <div className="dw-card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              High Priority
            </div>
            <div className="text-2xl font-bold text-amber-600 mt-1">
              {highCount}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Notable positioning shifts
            </div>
          </div>
          <div className="dw-card p-4">
            <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
              Routine Updates
            </div>
            <div className="text-2xl font-bold text-emerald-600 mt-1">
              {routineCount}
            </div>
            <div className="text-[11px] text-slate-500 mt-1">
              Low/Medium tweaks
            </div>
          </div>
        </div>

        {/* Category Breakdown & Strategic Summary */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="dw-card p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">
              Change Categories Distribution
            </h3>

            {categoryEntries.length === 0 ? (
              <p className="text-xs text-slate-400 py-8 text-center">
                No categorical change data recorded yet.
              </p>
            ) : (
              <div className="space-y-3 pt-2">
                {categoryEntries.map(([cat, count]) => {
                  const pct = Math.round((count / maxCategoryCount) * 100);
                  return (
                    <div key={cat} className="space-y-1">
                      <div className="flex justify-between text-xs">
                        <span className="font-semibold text-slate-700 capitalize">
                          {cat}
                        </span>
                        <span className="text-slate-500 font-mono">
                          {count} ({Math.round((count / totalChanges) * 100)}%)
                        </span>
                      </div>
                      <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
                        <div
                          className="bg-blue-600 h-2 rounded-full"
                          style={{ width: `${Math.max(pct, 5)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Strategic Analysis & Recommendations */}
          <div className="dw-card p-5 space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">
              Strategic Observations
            </h3>

            <div className="space-y-3 text-xs">
              {criticalCount > 0 ? (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-900 space-y-1">
                  <div className="font-semibold">⚠️ Critical Changes Detected</div>
                  <p>
                    {criticalCount} change(s) marked critical. Review pricing or positioning changes immediately on the Changes tab.
                  </p>
                </div>
              ) : (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-md text-emerald-900 space-y-1">
                  <div className="font-semibold">✓ Stable Pricing Landscape</div>
                  <p>
                    No critical competitor anomalies detected in the current monitoring window.
                  </p>
                </div>
              )}

              <div className="p-3 bg-blue-50 border border-blue-200 rounded-md text-blue-900 space-y-1">
                <div className="font-semibold">💡 Active Monitoring Coverage</div>
                <p>
                  DriftWatch is tracking {sources.length} competitor domain(s). For deeper query analysis, use the <b>Ask AI</b> assistant.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

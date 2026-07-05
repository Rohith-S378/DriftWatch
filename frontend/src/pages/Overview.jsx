import Navbar from "../components/Navbar";
import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  listCompetitors,
  addCompetitor,
  removeCompetitor,
  triggerCrawl,
  crawlSingle,
  getChangeHistory
} from "../api.js";

function Overview({ sources }) {
  const [company, setCompany] = useState("");
  const [url, setUrl] = useState("");
  const [competitors, setCompetitors] = useState({});
  const [loading, setLoading] = useState(false);
  const [crawlResult, setCrawlResult] = useState(null);
  const [error, setError] = useState(null);
  const [liveEvents, setLiveEvents] = useState([]); // array of recent events
  const [liveLoading, setLiveLoading] = useState(false);
  const [liveError, setLiveError] = useState(null);

  const navigate = useNavigate();
  const domain = localStorage.getItem("domain");

  async function loadCompetitors() {
    try {
      const data = await listCompetitors();
      // Only update if data actually changed to prevent infinite loop
      if (JSON.stringify(data) !== JSON.stringify(competitors)) {
        setCompetitors(data);
      }
    } catch (err) {
      console.error('Failed to load competitors:', err);
      setError('Failed to load competitors. Please try again later.');
    }
  }

  // Fetch recent events for all competitors
  async function fetchLiveEvents() {
    if (Object.keys(competitors).length === 0) {
      setLiveEvents([]);
      return;
    }
    setLiveLoading(true);
    setLiveError(null);
    try {
      const eventsMap = {};
      // Fetch for each competitor (limit to last 5 events each)
      const promises = Object.entries(competitors).map(async ([name, url]) => {
        try {
          const data = await getChangeHistory(name); // sourceId is competitor name
          // Assuming getChangeHistory returns array of events sorted descending
          if (!data.error) {
            eventsMap[name] = data.slice(0, 5); // take latest 5
          } else {
            console.warn(`Failed to fetch events for ${name}:`, data.error);
            eventsMap[name] = [];
          }
        } catch (err) {
          console.error(`Error fetching events for ${name}:`, err);
          eventsMap[name] = [];
        }
      });
      await Promise.all(promises);
      // Flatten events with source label
      const allEvents = [];
      Object.entries(eventsMap).forEach(([source, events]) => {
        events.forEach(ev => {
          allEvents.push({ ...ev, source });
        });
      });
      // Sort by timestamp descending
      allEvents.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
      // Keep only top 20 most recent
      setLiveEvents(allEvents.slice(0, 20));
    } catch (err) {
      console.error('Error fetching live events:', err);
      setLiveError('Failed to load live events');
    } finally {
      setLiveLoading(false);
    }
  }

  useEffect(() => {
    loadCompetitors();
    // Fetch live events initially
    fetchLiveEvents();
    // Set interval to update every 10 seconds
    const intervalId = setInterval(fetchLiveEvents, 10000);
    return () => clearInterval(intervalId);
  }, [competitors]); // re-run effect if competitors change

  async function handleSubmit() {
    if (!company || !url) {
      setError("Please fill all fields");
      return;
    }

    setLoading(true);
    setError(null);
    const result = await addCompetitor(company, url);
    if (result.error) {
      setError(result.error);
      setLoading(false);
      return;
    }
    if (!result) {
      setError("Failed to add competitor (unexpected error)");
      setLoading(false);
      return;
    }

    const crawl = await crawlSingle(company, url);
    setCrawlResult(crawl);

    try {
      await loadCompetitors();
    } catch (err) {
      // Error already handled in loadCompetitors
    }

    if (window.refreshData) await window.refreshData();

    localStorage.setItem("company", company);
    localStorage.setItem("url", url);
    setLoading(false);
  }

  const handleQuickCrawl = async (name) => {
    setLoading(true);
    await triggerCrawl(name);
    try {
      await loadCompetitors();
    } catch (err) {
      // Error already handled in loadCompetitors
    }
    setLoading(false);
    if (window.refreshData) window.refreshData();
  };

  const handleRemove = async (name) => {
    await removeCompetitor(name);
    try {
      await loadCompetitors();
    } catch (err) {
      // Error already handled in loadCompetitors
    }
    if (window.refreshData) await window.refreshData();
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <Navbar />

      <div className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Market Intelligence Dashboard</h1>
        <p className="text-muted">Track competitors, pricing changes, and market positioning</p>
      </div>

      {/* Live Crawling Dashboard */}
      <div className="glass-card p-4 mb-4">
        <h3 className="font-semibold mb-2 flex items-center gap-2">
          📡 Live Crawling Activity
        </h3>
        {liveLoading && (
          <p className="mb-4 text-center text-sm">
            Loading recent activity...
          </p>
        )}
        {!liveLoading && liveEvents.length > 0 && (
          <div className="space-y-3">
            {liveEvents.map((event, idx) => (
              <div key={event.id || idx} className="p-2 border-l-2 border-blue-500 bg-blue-50 dark:bg-blue-50 dark:border-blue-200">
                <div className="flex justify-between items-start mb-1">
                  <div className="flex items-center space-x-1">
                    <span className="text-xs font-medium text-blue-800 dark:text-blue-900">{event.source}</span>
                    <span className="text-xs text-muted">{new Date(event.created_at).toLocaleTimeString()}</span>
                  </div>
                  {(() => {
                    const badgeStyles = {
                      critical: { bg: '#fee2e2', text: '#991b1b' },
                      high: { bg: '#fee2e2', text: '#b91c1c' },
                      medium: { bg: '#fef3c7', text: '#92400e' },
                      low: { bg: '#f3f4f6', text: '#4b5563' },
                    };
                    const s = badgeStyles[event.severity] || badgeStyles.low;
                    return (
                      <span
                        className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{ backgroundColor: s.bg, color: s.text }}
                      >
                        {event.severity ? event.severity.charAt(0).toUpperCase() + event.severity.slice(1) : "Low"}
                      </span>
                    );
                  })()}
                </div>
                <p className="text-sm text-gray-700 dark:text-gray-300">{event.description}</p>
                {(event.old_value || event.new_value) && (
                  <div className="mt-1 text-xs space-x-1">
                    {event.old_value && (
                      <span className="bg-red-50 text-red-800 px-1 py-0.5 rounded">− {String(event.old_value).substring(0, 30)}{String(event.old_value).length > 30 ? '…' : ''}</span>
                    )}
                    {event.new_value && (
                      <span className="bg-green-50 text-green-800 px-1 py-0.5 rounded">+ {String(event.new_value).substring(0, 30)}{String(event.new_value).length > 30 ? '…' : ''}</span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
        {!liveLoading && liveEvents.length === 0 && (
          <p className="text-center text-muted">No recent crawling activity.</p>
        )}
      </div>

      
      {/* Show selected domain */}
      <div className="mb-4">
        Selected Domain: <b className="text-accent">{domain || "None"}</b>
      </div>

      {/* Add Competitor Section */}
      <div className="glass-card p-6 mb-6">
        <h3 className="font-semibold mb-4">🔍 Add Competitor</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">Competitor Name</label>
            <input
              type="text"
              placeholder="e.g., Byjus"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
              className="input w-full"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">Website URL</label>
            <input
              type="text"
              placeholder="e.g., https://byjus.com/pricing"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              className="input w-full"
            />
          </div>

          {error && (
            <p className="text-error text-sm">{error}</p>
          )}

          <button
            onClick={handleSubmit}
            disabled={loading}
            className={`btn btn-primary w-full ${loading ? 'opacity-70 cursor-not-allowed' : ''}`}
          >
            {loading ? "Adding & Crawling..." : "Add & Analyze Competitor"}
          </button>
        </div>
      </div>

      {/* Crawl Result */}
      {crawlResult && crawlResult.success && (
        <div className="glass-card p-6 mb-6">
          <h4 className="font-semibold mb-2 text-success">✅ Crawl Successful!</h4>
          <div className="space-y-2 text-sm">
            <p><b>Headline:</b> {crawlResult.headline || "N/A"}</p>
            <p><b>Pricing Tiers Found:</b> {crawlResult.pricing?.length || 0}</p>
            <p><b>Keywords:</b> {crawlResult.keywords?.join(", ") || "N/A"}</p>
          </div>
        </div>
      )}

      {/* Registered Competitors */}
      <div className="glass-card p-6 mb-6">
        {/* Get valid competitors object or empty object if invalid */}
        {!competitors || typeof competitors !== 'object' ? (
          <p className="text-muted">No competitors added yet. Add one above!</p>
        ) : (
          <>
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              📊 Tracked Competitors ({Object.keys(competitors).length})
              {!Object.keys(competitors).length && (
                <span className="text-xs text-muted">(add competitors above)</span>
              )}
            </h3>

            {Object.keys(competitors).length === 0 ? (
              <p className="text-muted">No competitors added yet. Add one above!</p>
            ) : (
              <div className="space-y-3">
                {Object.entries(competitors).map(([name, url]) => (
                  <div key={name} className="p-4 border rounded-lg border-gray-200">
                    <div className="flex justify-between items-start mb-2">
                    <div className="font-medium">{name}</div>
                    <div className="text-xs text-muted truncate max-w-xs">{url}</div>
                  </div>
                    <div className="flex gap-3 mt-3">
                      <button
                        onClick={() => handleQuickCrawl(name)}
                        disabled={loading}
                        className="btn btn-success px-3 py-1 text-xs"
                      >
                        Crawl Now
                      </button>
                      <button
                        onClick={() => handleRemove(name)}
                        className="btn btn-error px-3 py-1 text-xs"
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </>
        )}

        <div className="mt-6">
          <button
            onClick={() => navigate("/insights")}
            className="btn btn-primary w-full"
          >
            View Insights →
          </button>
        </div>
      </div>
    </div>
  );
}

export default Overview;
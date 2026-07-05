// frontend/src/api.js
// CREATE THIS FILE — central API connector

// ── BASE URL ──────────────────────────────────────────────────────────────────
// This points to your Python FastAPI backend
// During development: http://localhost:8000
// Change this ONE line if the port changes — nothing else needs updating
const BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// ── HELPER ────────────────────────────────────────────────────────────────────
async function apiFetch(path, options = {}) {
  try {
    const response = await fetch(`${BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.status} on ${path}`);
    }

    return await response.json();

  } catch (error) {
    // If backend is down, return safe fallback data
    // This prevents the UI from crashing during demo
    console.error(`API call failed for ${path}:`, error.message);
    return null;
  }
}

// ── API FUNCTIONS ─────────────────────────────────────────────────────────────
// P3 calls these functions — they never write fetch() directly

export async function getSnapshots() {
  const data = await apiFetch("/snapshots");
  // Return empty array if backend is down — UI won't crash
  return data || [];
}

export async function getChanges() {
  const data = await apiFetch("/changes");
  return data || [];
}

export async function getInsights() {
  const data = await apiFetch("/insights");
  return data || { insights: "", gaps: [], profiles: [] };
}

export async function askQuestion(question) {
  const data = await apiFetch("/ask", {
    method:  "POST",
    body:    JSON.stringify({ question }),
  });
  return data || { answer: "Backend unavailable. Please try again." };
}

export async function checkHealth() {
  const data = await apiFetch("/health");
  return data !== null;
}

export async function ingestData(companyData) {
  const data = await apiFetch("/ingest", {
    method: "POST",
    body:   JSON.stringify(companyData),
  });
  return data || { ok: false };
}

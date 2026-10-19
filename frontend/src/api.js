// frontend/src/api.js
// Centralized API client with credentials (cookies) and CSRF protection.

const PYTHON_API = "http://localhost:8000";

// Read CSRF token from dw_csrf cookie set by the server
function getCsrfToken() {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp("(^|;\\s*)dw_csrf=([^;]*)"));
  return match ? decodeURIComponent(match[2]) : null;
}

async function safeFetch(url, options = {}) {
  try {
    const res = await fetch(url, {
      credentials: "include", // send/receive HttpOnly session cookie
      ...options,
      headers: {
        Accept: "application/json",
        ...(options.headers || {}),
      },
    });
    if (!res.ok) {
      const text = await res.text();
      let errorDetail = text;
      try {
        const parsed = JSON.parse(text);
        errorDetail = parsed.detail || parsed.message || text;
      } catch (e) {
        // use raw text
      }
      return { error: errorDetail, status: res.status };
    }
    return await res.json();
  } catch (e) {
    console.error(`Fetch failed: ${url}`, e.message);
    return { error: e.message, status: 0 };
  }
}

async function safePost(url, body, method = "POST") {
  try {
    const headers = {
      "Content-Type": "application/json",
      Accept: "application/json",
    };
    const csrf = getCsrfToken();
    if (csrf) {
      headers["X-CSRF-Token"] = csrf;
    }

    const res = await fetch(url, {
      method: method,
      credentials: "include",
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      const text = await res.text();
      let errorDetail = text;
      try {
        const parsed = JSON.parse(text);
        errorDetail = parsed.detail || parsed.message || text;
      } catch (e) {
        // use raw text
      }
      return { error: errorDetail, status: res.status };
    }
    return await res.json();
  } catch (e) {
    console.error(`${method} failed: ${url}`, e.message);
    return { error: e.message, status: 0 };
  }
}

// ── AUTHENTICATION API ──────────────────────────────────────────────────────

export async function getAuthStatus() {
  return await safeFetch(`${PYTHON_API}/api/auth/status`);
}

export async function getCurrentUser() {
  return await safeFetch(`${PYTHON_API}/api/auth/me`);
}

export async function registerUser({ email, password, display_name }) {
  return await safePost(`${PYTHON_API}/api/auth/register`, {
    email,
    password,
    display_name,
  });
}

export async function loginUser({ email, password }) {
  return await safePost(`${PYTHON_API}/api/auth/login`, {
    email,
    password,
  });
}

export async function logoutUser() {
  return await safePost(`${PYTHON_API}/api/auth/logout`, {});
}

export async function getAuthProviders() {
  return await safeFetch(`${PYTHON_API}/api/auth/providers`);
}

export async function initiateGoogleLogin() {
  return await safeFetch(`${PYTHON_API}/api/auth/google/login`);
}

// ── BUSINESS APIS ───────────────────────────────────────────────────────────

export async function checkPythonHealth() {
  const data = await safeFetch(`${PYTHON_API}/health`);
  return data !== null && !data.error && data.status === "ok";
}

export async function getSources() {
  const data = await safeFetch(`${PYTHON_API}/api/sources`);
  return data.error ? [] : (data?.sources || []);
}

export async function getAllEvents(limit = 100) {
  const data = await safeFetch(`${PYTHON_API}/api/events?limit=${limit}`);
  return data.error ? [] : data;
}

export async function getChangeHistory(sourceId) {
  const data = await safeFetch(
    `${PYTHON_API}/webhook/events/${encodeURIComponent(sourceId)}?limit=50`
  );
  return data.error ? [] : data;
}

export async function addCompetitor(name, url) {
  return await safePost(`${PYTHON_API}/api/competitors/add`, { name, url });
}

export async function listCompetitors() {
  const data = await safeFetch(`${PYTHON_API}/api/competitors`);
  const list = data.error ? [] : (data?.competitors || []);
  const normalized = {};
  for (const c of list) {
    if (c && c.source_id) normalized[c.source_id] = c.url;
  }
  return normalized;
}

export async function removeCompetitor(name) {
  return await safePost(
    `${PYTHON_API}/api/competitors/${encodeURIComponent(name)}`,
    null,
    "DELETE"
  );
}

export async function triggerCrawl(sourceId = null) {
  const url = sourceId
    ? `${PYTHON_API}/api/crawl/trigger?source_id=${encodeURIComponent(sourceId)}`
    : `${PYTHON_API}/api/crawl/trigger`;
  return await safePost(url, {});
}

export async function crawlSingle(sourceId, url) {
  return await safePost(`${PYTHON_API}/api/crawl/single`, {
    source_id: sourceId,
    url: url,
  });
}

export async function askAI({ question, source_id = null }) {
  return await safePost(`${PYTHON_API}/api/ai/query`, { question, source_id });
}

export async function analyzeAndDiscover(url) {
  return await safePost(`${PYTHON_API}/api/discovery/analyze`, { url });
}

export async function listDiscoveryRuns() {
  const data = await safeFetch(`${PYTHON_API}/api/discovery/runs`);
  return data.error ? [] : data;
}

export async function getDiscoveryRun(runId) {
  return await safeFetch(`${PYTHON_API}/api/discovery/runs/${runId}`);
}

export async function trackDiscoveryCandidate(candidateId, customName = null) {
  return await safePost(`${PYTHON_API}/api/discovery/track`, {
    candidate_id: candidateId,
    custom_name: customName,
  });
}

export async function dismissDiscoveryCandidate(candidateId) {
  return await safePost(`${PYTHON_API}/api/discovery/dismiss/${candidateId}`, {});
}

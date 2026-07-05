// frontend/src/api.js  ← CREATE THIS FILE

const PYTHON_API = "http://localhost:8000"   // FastAPI
const NODE_API   = "http://localhost:3000"   // Node.js

async function safeFetch(url) {
  try {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`${res.status}`)
    return await res.json()
  } catch (e) {
    console.error(`Failed: ${url}`, e.message)
    return { error: e.message, status: e.message }
  }
}

async function safePost(url, body) {
  try {
    const res = await fetch(url, {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify(body),
    })
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
    return await res.json()
  } catch (e) {
    console.error(`POST failed: ${url}`, e.message)
    return { error: e.message }
  }
}

// ── FROM PYTHON BACKEND ───────────────────────────────────────────────────────

export async function checkPythonHealth() {
  const data = await safeFetch(`${PYTHON_API}/health`)
  return data !== null && !data.error
}

export async function getSnapshots() {
  const data = await safeFetch(`${PYTHON_API}/api/snapshots`)
  return data.error ? [] : data
}

export async function getSources() {
  const data = await safeFetch(`${PYTHON_API}/api/sources`)
  return data.error ? [] : (data?.sources || [])
}

export async function getChangeHistory(sourceId) {
  const data = await safeFetch(
    `${PYTHON_API}/webhook/events/${sourceId}?limit=50`
  )
  return data.error ? [] : data
}

// Send scraper data directly to Python webhook
export async function ingestScraperData(sourceId, sourceType, data) {
  return await safePost(`${PYTHON_API}/webhook/ingest`, {
    source_id:   sourceId,
    source_type: sourceType,
    data:        data,
  })
}

// ── CRAWLER API (NEW) ───────────────────────────────────────────────────────

export async function addCompetitor(name, url) {
  return await safePost(`${PYTHON_API}/api/competitors/add`, { name, url })
}

export async function listCompetitors() {
  const data = await safeFetch(`${PYTHON_API}/api/competitors`)
  const list = data.error ? [] : (data?.competitors || [])
  // Backend returns a LIST of {source_id, url} objects, not a dict keyed
  // by name. Normalize it here so every consumer (Overview.jsx, App.jsx)
  // can keep doing Object.entries(competitors) / Object.keys(competitors)
  // and get real names/urls instead of array indices and raw objects.
  const normalized = {}
  for (const c of list) {
    if (c && c.source_id) normalized[c.source_id] = c.url
  }
  return normalized
}

export async function removeCompetitor(name) {
  try {
    const res = await fetch(`${PYTHON_API}/api/competitors/${encodeURIComponent(name)}`, {
      method: "DELETE"
    })
    if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`)
    return await res.json()
  } catch (e) {
    console.error("Failed to remove competitor:", e.message)
    return { error: e.message }
  }
}

export async function triggerCrawl(sourceId = null) {
  const url = sourceId
    ? `${PYTHON_API}/api/crawl/trigger?source_id=${encodeURIComponent(sourceId)}`
    : `${PYTHON_API}/api/crawl/trigger`
  return await safePost(url, {})
}

export async function crawlSingle(sourceId, url) {
  return await safePost(`${PYTHON_API}/api/crawl/single`, { source_id: sourceId, url })
}

// ── FROM NODE.JS LAYER ────────────────────────────────────────────────────────

export async function checkNodeHealth() {
  const data = await safeFetch(`${NODE_API}/health`)
  return data !== null && !data.error
}

export async function getRecentEvents() {
  const data = await safeFetch(`${NODE_API}/api/events`)
  return data.error ? [] : data
}

export async function getEventsBySource(sourceId) {
  const data = await safeFetch(`${NODE_API}/api/events/${sourceId}`)
  return data.error ? [] : data
}
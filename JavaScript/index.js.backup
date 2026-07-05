// ADD to your JavaScript/server or index.js

const express = require('express')
const cors    = require('cors')

// ADD cors middleware — React can't call Node without this
app.use(cors({
  origin: [
    'http://localhost:5173',   // React Vite
    'http://localhost:5174',
    '*'
  ]
}))

// In-memory store for received events (simple, no DB needed on Node side)
let receivedEvents = []

// Your existing route that Python POSTs to — ADD storing logic
app.post('/internal/change-events', (req, res) => {
  const event = req.body
  // Store it so frontend can read it
  receivedEvents.unshift({ ...event, received_at: new Date().toISOString() })
  // Keep only last 100
  if (receivedEvents.length > 100) receivedEvents = receivedEvents.slice(0, 100)

  console.log('Change event received:', event.source_id, event.change_type)
  res.json({ ok: true })
})

// ADD these new routes for the React frontend to call
app.get('/api/events', (req, res) => {
  res.json(receivedEvents)
})

app.get('/api/events/:sourceId', (req, res) => {
  const filtered = receivedEvents.filter(
    e => e.source_id === req.params.sourceId
  )
  res.json(filtered)
})

app.get('/health', (req, res) => {
  res.json({ status: 'ok', events_stored: receivedEvents.length })
})

// frontend/src/App.jsx
import { useEffect, useState } from "react"
import {
  checkPythonHealth,
  getSources,
  getChangeHistory,
 listCompetitors,        // ADD THIS IMPORT
} from "./api.js"
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Overview from "./pages/Overview";
import Insights from "./pages/Insights";
import Changes from "./pages/Changes";
import AskAI from "./pages/askAI";
import DomainSelect from "./pages/DomainSelect";

function App() {
  const [pythonOk, setPythonOk] = useState(null)
  const [sources, setSources] = useState([])
  const [events, setEvents] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadAll()
  }, [])

  async function loadAll() {
    setLoading(true)

    const py = await checkPythonHealth()
    setPythonOk(py)

    // CHANGED: only pull events for competitors you actually registered,
    // not every source_id that has ever existed in the DB (which includes
    // old demo/seed data from udemy/scaler/coursera/gfg).
    const registered = await listCompetitors()      // { name: url, ... }
    const activeSourceIds = Object.keys(registered)
    setSources(activeSourceIds)

    const allEvents = []
    for (const src of activeSourceIds) {
      const evts = await getChangeHistory(src)
      allEvents.push(...evts)
    }
    setEvents(allEvents)
    setLoading(false)
  }

  window.refreshData = loadAll

  return (
    <div className="app-container">
      <div className="fixed top-4 right-4 flex items-center gap-2 text-xs rounded px-3 py-1"
           style={{
             backgroundColor: pythonOk ? "var(--success)" : "var(--error)",
             color: "white"
           }}>
        Backend: {pythonOk ? "Connected" : "Disconnected"}
        {loading && " (Loading...)"}
      </div>

      <BrowserRouter>
        <Routes>
          <Route path="/" element={<DomainSelect />} />
          <Route path="/overview" element={<Overview sources={sources} />} />
          <Route path="/insights" element={<Insights events={events} sources={sources} />} />
          <Route path="/changes" element={<Changes events={events} sources={sources} />} />
          <Route path="/ask" element={<AskAI />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
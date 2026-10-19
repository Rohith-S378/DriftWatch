// frontend/src/App.jsx
// Main application router with AuthProvider, ProtectedRoutes, and Light-Theme Shell

import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Account from "./pages/Account";
import DomainSelect from "./pages/DomainSelect";
import Overview from "./pages/Overview";
import Discovery from "./pages/Discovery";
import Changes from "./pages/Changes";
import Insights from "./pages/Insights";
import AskAI from "./pages/AskAI";

import { checkPythonHealth, listCompetitors, getChangeHistory } from "./api";

function AppContent() {
  const [pythonOk, setPythonOk] = useState(null);
  const [sources, setSources] = useState([]);
  const [events, setEvents] = useState([]);

  async function loadData() {
    const py = await checkPythonHealth();
    setPythonOk(py);

    try {
      const registered = await listCompetitors();
      const activeSourceIds = Object.keys(registered);
      setSources(activeSourceIds);

      const allEvents = [];
      for (const src of activeSourceIds) {
        const evts = await getChangeHistory(src);
        if (Array.isArray(evts)) {
          allEvents.push(...evts);
        }
      }
      setEvents(allEvents);
    } catch (err) {
      console.error("Failed to load competitor data:", err);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, []);

  window.refreshData = loadData;

  return (
    <Routes>
      {/* Public Authentication routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />

      {/* Protected application routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DomainSelect pythonOk={pythonOk} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/overview"
        element={
          <ProtectedRoute>
            <Overview pythonOk={pythonOk} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/discovery"
        element={
          <ProtectedRoute>
            <Discovery pythonOk={pythonOk} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/changes"
        element={
          <ProtectedRoute>
            <Changes events={events} sources={sources} pythonOk={pythonOk} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/insights"
        element={
          <ProtectedRoute>
            <Insights events={events} sources={sources} pythonOk={pythonOk} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/ask"
        element={
          <ProtectedRoute>
            <AskAI pythonOk={pythonOk} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/account"
        element={
          <ProtectedRoute>
            <Account pythonOk={pythonOk} />
          </ProtectedRoute>
        }
      />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/overview" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppContent />
      </BrowserRouter>
    </AuthProvider>
  );
}

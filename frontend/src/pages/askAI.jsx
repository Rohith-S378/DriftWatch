// frontend/src/pages/AskAI.jsx
// Prompt.txt Section 6 Page F compliant Ask AI Page

import { useState } from "react";
import AppLayout from "../components/AppLayout";
import { askAI } from "../api";

export default function AskAI({ pythonOk }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [evidence, setEvidence] = useState([]);
  const [error, setError] = useState("");

  const suggestedQuestions = [
    "What changed in competitor pricing this week?",
    "Which competitors added new features recently?",
    "Summarize recent positioning updates across all tracked competitors.",
  ];

  const handleAsk = async (queryText) => {
    const q = (queryText || question).trim();
    if (!q) {
      setError("Please enter a question.");
      return;
    }

    setLoading(true);
    setAnswer("");
    setEvidence([]);
    setError("");

    try {
      const res = await askAI({ question: q });
      if (res.error) {
        throw new Error(res.error);
      }
      setAnswer(res.answer || "No relevant data found for this question.");
      setEvidence(res.evidence || []);
    } catch (err) {
      console.error("Ask AI failed:", err);
      setError(err.message || "Failed to query intelligence engine.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <AppLayout pythonOk={pythonOk}>
      <div className="space-y-6 max-w-4xl">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Ask AI
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Ask questions grounded in your monitored competitive data and inspect supporting evidence.
          </p>
        </div>

        {/* Suggested Prompts (Prompt.txt Section 6 Page F) */}
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-2">
            Suggested Queries
          </div>
          <div className="flex flex-wrap gap-2">
            {suggestedQuestions.map((sq, i) => (
              <button
                key={i}
                onClick={() => {
                  setQuestion(sq);
                  handleAsk(sq);
                }}
                className="dw-btn dw-btn-secondary text-xs px-3 py-1.5 bg-white hover:bg-slate-50"
              >
                {sq}
              </button>
            ))}
          </div>
        </div>

        {/* Query Input Card */}
        <div className="dw-card p-4 space-y-3">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleAsk();
            }}
            className="flex gap-2"
          >
            <input
              type="text"
              placeholder="Ask about your competitors' pricing, plans, or keywords..."
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={loading}
              className="dw-input flex-1 text-xs"
            />
            <button
              type="submit"
              disabled={loading}
              className="dw-btn dw-btn-primary px-5 text-xs font-semibold"
            >
              {loading ? "Analyzing..." : "Ask"}
            </button>
          </form>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded text-xs text-red-700">
              {error}
            </div>
          )}
        </div>

        {/* Answer & Evidence Section */}
        {answer && (
          <div className="dw-card p-6 space-y-5">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-blue-600 bg-blue-50 px-2 py-0.5 rounded inline-block mb-2">
                Grounded Intelligence Answer
              </div>
              <p className="text-xs text-slate-800 leading-relaxed whitespace-pre-wrap font-medium">
                {answer}
              </p>
            </div>

            {evidence && evidence.length > 0 && (
              <div className="border-t border-slate-100 pt-4 space-y-3">
                <div className="text-xs font-semibold text-slate-900">
                  Supporting Evidence ({evidence.length} record
                  {evidence.length === 1 ? "" : "s"})
                </div>
                <div className="space-y-2">
                  {evidence.map((ev, i) => (
                    <div
                      key={ev.id || i}
                      className="p-3 bg-slate-50 border border-slate-200 rounded text-xs space-y-1"
                    >
                      <div className="flex justify-between items-center">
                        <span className="font-semibold text-slate-800">
                          {ev.source_id}
                        </span>
                        <span className="dw-badge dw-badge-low">
                          {ev.change_type} · {ev.severity}
                        </span>
                      </div>
                      <p className="text-slate-600">{ev.description}</p>
                      {ev.created_at && (
                        <div className="text-[10px] text-slate-400">
                          Detected: {new Date(ev.created_at).toLocaleString()}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}

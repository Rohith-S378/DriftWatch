import Navbar from "../components/Navbar";
import { useState } from "react";
import { askAI } from "../api";

function AskAI() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [answer, setAnswer] = useState("");
  const [evidence, setEvidence] = useState([]);
  const [error, setError] = useState("");

  const handleAsk = async () => {
    const q = question.trim();
    if (!q) {
      setAnswer("");
      setEvidence([]);
      setError("Please enter a question first.");
      return;
    }

    setLoading(true);
    setAnswer("");
    setEvidence([]);
    setError("");

    try {
      const res = await askAI({ question: q });
      setAnswer(res.answer || "");
      setEvidence(res.evidence || []);
      if (!res.answer) {
        setError("No answer returned from the backend.");
      }
    } catch (err) {
      console.error("Ask AI request failed:", err);
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to query the AI intelligence engine. Is the backend running?"
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Navbar />
      <h2 className="text-2xl font-bold mb-4">Ask AI</h2>

      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Ask a question about competitor changes (e.g. 'What changed in pricing this week?')"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="input"
          onKeyDown={(e) => {
            if (e.key === "Enter") handleAsk();
          }}
        />
        <button
          onClick={handleAsk}
          disabled={loading}
          className="btn btn-primary px-4 py-2"
        >
          {loading ? "Thinking..." : "Ask"}
        </button>
      </div>

      {error && (
        <div className="glass-card p-4 border-l-4 border-red-500">
          <p className="text-red-600 font-medium">Error</p>
          <p className="text-muted text-sm">{error}</p>
        </div>
      )}

      {answer && (
        <div className="glass-card p-4 space-y-4">
          <div>
            <h3 className="font-semibold text-lg mb-2">Answer</h3>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{answer}</p>
          </div>

          {evidence.length > 0 && (
            <div>
              <h4 className="font-semibold text-sm mb-2">
                Supporting Evidence ({evidence.length} event{evidence.length === 1 ? "" : "s"})
              </h4>
              <div className="space-y-2">
                {evidence.map((ev) => (
                  <div
                    key={ev.id}
                    className="p-3 bg-gray-50 rounded-lg border-l-4 border-indigo-500"
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <span className="font-medium text-sm">{ev.source_id}</span>
                        <span className="text-xs text-muted ml-2">
                          {ev.change_type} · {ev.severity}
                        </span>
                      </div>
                      {ev.created_at && (
                        <span className="text-xs text-muted">
                          {new Date(ev.created_at).toLocaleString()}
                        </span>
                      )}
                    </div>
                    <p className="text-sm mt-1">{ev.description}</p>
                    {(ev.old_value || ev.new_value) && (
                      <div className="mt-2 text-xs space-y-1">
                        {ev.old_value && (
                          <div className="text-red-600">− {ev.old_value}</div>
                        )}
                        {ev.new_value && (
                          <div className="text-green-600">+ {ev.new_value}</div>
                        )}
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
  );
}

export default AskAI;
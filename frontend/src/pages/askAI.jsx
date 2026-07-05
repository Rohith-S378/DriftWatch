import Navbar from "../components/Navbar";
import { useState } from "react";

function AskAI() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  const handleAsk = () => {
    if (!question) {
      setAnswer("Please enter a question first.");
    } else {
      setAnswer(`Insight: ${question} → Competitors focus on short courses.`);
    }
  };

  return (
    <div className="space-y-4">
      <Navbar />
      <h2 className="text-2xl font-bold mb-4">Ask AI</h2>

      <div className="flex items-center gap-3">
        <input
          type="text"
          placeholder="Ask a question..."
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          className="input"
        />
        <button
          onClick={handleAsk}
          className="btn btn-primary px-4 py-2"
        >
          Ask
        </button>
      </div>

      {answer && (
        <div className="glass-card p-4">
          {answer}
        </div>
      )}
    </div>
  );
}

export default AskAI;
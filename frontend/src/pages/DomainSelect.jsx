// frontend/src/pages/DomainSelect.jsx
// Prompt.txt Section 6 Page G compliant Domain Onboarding Page

import { useState } from "react";
import { useNavigate } from "react-router-dom";
import AppLayout from "../components/AppLayout";

export default function DomainSelect({ pythonOk }) {
  const navigate = useNavigate();
  const [domainUrl, setDomainUrl] = useState("");
  const [error, setError] = useState("");
  const [currentDomain, setCurrentDomain] = useState(
    localStorage.getItem("domain") || ""
  );

  const predefinedDomains = [
    { label: "Competitive Exams & EdTech", value: "Competitive Exams" },
    { label: "Technical & Cloud Courses", value: "Technical Courses" },
    { label: "Higher Education Institutions", value: "Schools & Colleges" },
    { label: "B2B SaaS & Developer Tools", value: "B2B SaaS" },
  ];

  const handleSelectPredefined = (dom) => {
    localStorage.setItem("domain", dom);
    setCurrentDomain(dom);
    navigate("/overview");
  };

  const handleCustomSubmit = (e) => {
    e.preventDefault();
    if (!domainUrl.trim()) {
      setError("Please enter a valid website URL.");
      return;
    }
    try {
      const parsed = new URL(
        domainUrl.startsWith("http") ? domainUrl : `https://${domainUrl}`
      );
      localStorage.setItem("domain", parsed.hostname);
      setCurrentDomain(parsed.hostname);
      navigate("/discovery");
    } catch (err) {
      setError("Please enter a valid URL (e.g. company.com or https://company.com)");
    }
  };

  return (
    <AppLayout pythonOk={pythonOk}>
      <div className="max-w-2xl mx-auto py-8">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Start monitoring your competitive landscape
          </h1>
          <p className="text-xs text-slate-500 mt-1 max-w-md mx-auto">
            Tell DriftWatch your company website or sector. We'll crawl your site,
            extract your profile, and discover direct competitors to track.
          </p>
        </div>

        {/* Company Website Input Card */}
        <div className="dw-card p-6 mb-8">
          <form onSubmit={handleCustomSubmit} className="space-y-4">
            <div>
              <label
                htmlFor="domainUrl"
                className="block text-xs font-semibold text-slate-700 mb-1"
              >
                Your company website
              </label>
              <div className="flex gap-2">
                <input
                  id="domainUrl"
                  type="text"
                  placeholder="https://yourcompany.com"
                  value={domainUrl}
                  onChange={(e) => {
                    setDomainUrl(e.target.value);
                    setError("");
                  }}
                  className="dw-input flex-1"
                />
                <button
                  type="submit"
                  className="dw-btn dw-btn-primary px-5 font-medium text-xs"
                >
                  Continue →
                </button>
              </div>
              {error && (
                <p className="text-xs text-red-600 mt-1.5">{error}</p>
              )}
            </div>
            <p className="text-[11px] text-slate-400">
              We'll extract your value proposition and generate candidate competitors automatically.
            </p>
          </form>
        </div>

        {/* Or choose a predefined market sector */}
        <div className="dw-card p-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-4">
            Or select an existing market sector
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {predefinedDomains.map((item) => (
              <button
                key={item.value}
                onClick={() => handleSelectPredefined(item.value)}
                className={`p-3 text-left rounded-md border text-xs font-medium transition-all ${
                  currentDomain === item.value
                    ? "border-blue-600 bg-blue-50/50 text-blue-800"
                    : "border-slate-200 bg-white hover:bg-slate-50 text-slate-700"
                }`}
              >
                <div className="font-semibold">{item.label}</div>
                <div className="text-[11px] text-slate-400 mt-0.5">
                  Track pre-configured landscape
                </div>
              </button>
            ))}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

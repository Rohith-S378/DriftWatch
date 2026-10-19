// frontend/src/pages/Account.jsx
// Prompt.txt Section 10 compliant Account Settings Page

import { useState } from "react";
import { useAuth } from "../context/AuthContext";
import AppLayout from "../components/AppLayout";

export default function Account({ pythonOk }) {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState("profile");

  return (
    <AppLayout pythonOk={pythonOk}>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Account settings
          </h1>
          <p className="text-xs text-slate-500 mt-1">
            Manage your profile, authentication methods, and security preferences.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          {/* Navigation sidebar */}
          <div className="space-y-1">
            <button
              onClick={() => setActiveTab("profile")}
              className={`w-full text-left px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                activeTab === "profile"
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Account information
            </button>
            <button
              onClick={() => setActiveTab("security")}
              className={`w-full text-left px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                activeTab === "security"
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Security & Sessions
            </button>
            <button
              onClick={() => setActiveTab("connections")}
              className={`w-full text-left px-3 py-2 rounded-md text-xs font-medium transition-colors ${
                activeTab === "connections"
                  ? "bg-blue-50 text-blue-700 font-semibold"
                  : "text-slate-600 hover:bg-slate-100"
              }`}
            >
              Connected accounts
            </button>
          </div>

          {/* Tab content area */}
          <div className="md:col-span-3">
            {activeTab === "profile" && (
              <div className="dw-card p-6 space-y-5">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Profile details
                  </h3>
                  <p className="text-xs text-slate-500">
                    Your personal information and account identity.
                  </p>
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
                  <div>
                    <label className="block text-slate-500 mb-1">Display name</label>
                    <div className="p-2.5 bg-slate-50 rounded border border-slate-200 font-medium text-slate-800">
                      {user?.display_name || "— (not configured)"}
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-500 mb-1">Email address</label>
                    <div className="p-2.5 bg-slate-50 rounded border border-slate-200 font-mono text-slate-800">
                      {user?.email || "—"}
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-500 mb-1">User ID</label>
                    <div className="p-2.5 bg-slate-50 rounded border border-slate-200 font-mono text-slate-600 text-[11px] truncate">
                      {user?.id || "—"}
                    </div>
                  </div>
                  <div>
                    <label className="block text-slate-500 mb-1">Account status</label>
                    <div className="p-2.5 bg-slate-50 rounded border border-slate-200">
                      <span className="dw-badge dw-badge-success">Active</span>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === "security" && (
              <div className="dw-card p-6 space-y-6">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Session & Access Control
                  </h3>
                  <p className="text-xs text-slate-500">
                    Your session is managed server-side using secure HttpOnly cookies.
                  </p>
                </div>

                <div className="border border-slate-200 rounded-md p-4 bg-slate-50/50 space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-xs font-semibold text-slate-900">
                        Current Session
                      </div>
                      <div className="text-[11px] text-slate-500">
                        HttpOnly Cookie · 24-hour expiration · CSRF Protected
                      </div>
                    </div>
                    <span className="dw-badge dw-badge-success">Active</span>
                  </div>
                </div>

                <div>
                  <button
                    onClick={logout}
                    className="dw-btn dw-btn-danger text-xs font-medium"
                  >
                    Sign out of all sessions
                  </button>
                </div>
              </div>
            )}

            {activeTab === "connections" && (
              <div className="dw-card p-6 space-y-5">
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Connected accounts
                  </h3>
                  <p className="text-xs text-slate-500">
                    Link external authentication providers to your DriftWatch account.
                  </p>
                </div>

                <div className="border border-slate-200 rounded-md p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <svg className="w-5 h-5" viewBox="0 0 24 24">
                      <path
                        fill="#4285F4"
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                      />
                      <path
                        fill="#34A853"
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                      />
                      <path
                        fill="#FBBC05"
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
                      />
                      <path
                        fill="#EA4335"
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
                      />
                    </svg>
                    <div>
                      <div className="text-xs font-semibold text-slate-800">
                        Google
                      </div>
                      <div className="text-[11px] text-slate-400">
                        Sign in with Google OAuth 2.0
                      </div>
                    </div>
                  </div>
                  <span className="text-[11px] font-medium text-amber-700 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                    Not configured
                  </span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </AppLayout>
  );
}

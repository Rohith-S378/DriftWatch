// frontend/src/components/AppLayout.jsx
// Prompt.txt Section 4 compliant Desktop Sidebar + Top Header + Responsive Shell

import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function AppLayout({ children, pythonOk }) {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const navGroups = [
    {
      label: "MONITOR",
      items: [
        { path: "/overview", label: "Overview", icon: "📊" },
        { path: "/discovery", label: "Discovery", icon: "🔍" },
        { path: "/changes", label: "Changes", icon: "⚡" },
      ],
    },
    {
      label: "INTELLIGENCE",
      items: [
        { path: "/insights", label: "Insights", icon: "💡" },
        { path: "/ask", label: "Ask AI", icon: "🤖" },
      ],
    },
    {
      label: "SYSTEM",
      items: [
        { path: "/", label: "Domain Selection", icon: "🌐" },
        { path: "/account", label: "Account Settings", icon: "⚙️" },
      ],
    },
  ];

  const getBreadcrumb = () => {
    const currentPath = location.pathname;
    for (const group of navGroups) {
      for (const item of group.items) {
        if (item.path === currentPath) return `${group.label} / ${item.label}`;
      }
    }
    return "DriftWatch";
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col md:flex-row">
      {/* Desktop Sidebar (240px wide per wireframe) */}
      <aside className="hidden md:flex md:w-60 flex-col bg-white border-r border-slate-200 shrink-0">
        {/* Brand header */}
        <div className="h-14 flex items-center px-5 border-b border-slate-200 gap-2">
          <div className="w-6 h-6 rounded bg-blue-600 flex items-center justify-center text-white font-bold text-xs">
            DW
          </div>
          <span className="font-bold tracking-tight text-slate-900 text-base">DRIFTWATCH</span>
        </div>

        {/* Navigation Groups */}
        <nav className="flex-1 px-3 py-4 space-y-6 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.label}>
              <div className="px-3 mb-2 text-[11px] font-semibold tracking-wider text-slate-400 uppercase">
                {group.label}
              </div>
              <div className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive = location.pathname === item.path;
                  return (
                    <Link
                      key={item.path}
                      to={item.path}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-blue-50 text-blue-700 font-semibold"
                          : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/60"
                      }`}
                    >
                      <span className="text-base">{item.icon}</span>
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        {/* System status at bottom of sidebar */}
        <div className="p-3 border-t border-slate-200 bg-slate-50/50">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <span
                className={`w-2 h-2 rounded-full ${
                  pythonOk ? "bg-emerald-500" : "bg-red-500"
                }`}
              />
              Backend
            </span>
            <span className="font-mono text-[11px]">
              {pythonOk ? "Connected" : "Disconnected"}
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-14 bg-white border-b border-slate-200 px-4 md:px-6 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center gap-3">
            {/* Mobile menu hamburger toggle */}
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-1.5 rounded text-slate-600 hover:bg-slate-100"
              aria-label="Toggle navigation"
            >
              ☰
            </button>
            <span className="text-xs md:text-sm font-medium text-slate-500">
              {getBreadcrumb()}
            </span>
          </div>

          {/* Account profile & dropdown */}
          <div className="relative">
            {user ? (
              <button
                onClick={() => setAccountMenuOpen(!accountMenuOpen)}
                className="flex items-center gap-2.5 p-1 rounded-full hover:bg-slate-100 transition-colors"
                aria-expanded={accountMenuOpen}
              >
                <div className="w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-semibold text-xs flex items-center justify-center border border-blue-200">
                  {user.display_name
                    ? user.display_name.charAt(0).toUpperCase()
                    : user.email.charAt(0).toUpperCase()}
                </div>
                <div className="hidden sm:block text-left text-xs">
                  <div className="font-medium text-slate-800 leading-tight">
                    {user.display_name || user.email.split("@")[0]}
                  </div>
                  <div className="text-slate-400 text-[11px] leading-tight">
                    {user.email}
                  </div>
                </div>
              </button>
            ) : (
              <div className="flex items-center gap-2">
                <Link
                  to="/login"
                  className="text-xs font-medium text-slate-700 hover:text-slate-900 px-2 py-1"
                >
                  Sign in
                </Link>
                <Link
                  to="/register"
                  className="text-xs font-medium bg-blue-600 text-white rounded px-2.5 py-1 hover:bg-blue-700"
                >
                  Register
                </Link>
              </div>
            )}

            {/* Account Menu Dropdown (Wireframe Section 7) */}
            {accountMenuOpen && user && (
              <div
                className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg border border-slate-200 py-1.5 z-50"
                onMouseLeave={() => setAccountMenuOpen(false)}
              >
                <div className="px-4 py-2.5 border-b border-slate-100">
                  <div className="text-sm font-semibold text-slate-900">
                    {user.display_name || "DriftWatch User"}
                  </div>
                  <div className="text-xs text-slate-500 truncate">{user.email}</div>
                </div>

                <div className="py-1">
                  <Link
                    to="/account"
                    onClick={() => setAccountMenuOpen(false)}
                    className="flex items-center justify-between px-4 py-2 text-xs text-slate-700 hover:bg-slate-50"
                  >
                    <span>Account settings</span>
                    <span className="text-slate-400">›</span>
                  </Link>
                </div>

                <div className="border-t border-slate-100 pt-1">
                  <button
                    onClick={handleLogout}
                    className="w-full text-left px-4 py-2 text-xs font-medium text-red-600 hover:bg-red-50"
                  >
                    Sign out
                  </button>
                </div>
              </div>
            )}
          </div>
        </header>

        {/* Mobile menu tray */}
        {mobileMenuOpen && (
          <div className="md:hidden bg-white border-b border-slate-200 px-4 py-3 space-y-3">
            {navGroups.map((group) => (
              <div key={group.label} className="space-y-1">
                <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
                  {group.label}
                </div>
                {group.items.map((item) => (
                  <Link
                    key={item.path}
                    to={item.path}
                    onClick={() => setMobileMenuOpen(false)}
                    className="block px-3 py-1.5 rounded text-sm text-slate-700 hover:bg-slate-100"
                  >
                    {item.icon} {item.label}
                  </Link>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Main application body with full responsive layout */}
        <main className="flex-1 p-4 md:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}

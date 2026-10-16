"""
Start backend (uvicorn 8000), local test site (8088), and Vite dev server (5173)
for the Playwright browser E2E suite. Uses a fresh SQLite DB and ALLOW_LOCAL_CRAWLS=True.
Prints the PIDs one per line so the caller can terminate them.
"""
import subprocess, sys, os, time

ROOT = r"C:\Users\DELL\OneDrive\Documents\Default Project\driftwatch_local"
DB = os.path.join(ROOT, "e2e_browsers.db")
if os.path.exists(DB):
    os.remove(DB)

env = os.environ.copy()
env["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB}"
env["ALLOW_LOCAL_CRAWLS"] = "True"
env["WEBHOOK_SECRET"] = "test"
env["PYTHONPATH"] = ROOT
env["VITE_PYTHON_API"] = "http://localhost:8000"

procs = []

# 1. Backend
backend = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "app.main:app",
     "--host", "127.0.0.1", "--port", "8000"],
    cwd=ROOT, env=env,
    stdout=open(os.path.join(ROOT, "backend_browsers.log"), "w"),
    stderr=subprocess.STDOUT,
)
procs.append(backend)

# 2. Local test site
site = subprocess.Popen(
    [sys.executable, "e2e_site/server.py", "8088"],
    cwd=ROOT,
    stdout=open(os.path.join(ROOT, "e2e_site_browsers.log"), "w"),
    stderr=subprocess.STDOUT,
)
procs.append(site)

# 3. Vite dev server
vite = subprocess.Popen(
    [r"C:\Program Files\nodejs\npm.cmd", "run", "dev", "--", "--port", "5173", "--host", "127.0.0.1"],
    cwd=os.path.join(ROOT, "frontend"),
    env=env,
    stdout=open(os.path.join(ROOT, "vite_browsers.log"), "w"),
    stderr=subprocess.STDOUT,
)
procs.append(vite)

print("Started:", backend.pid, site.pid, vite.pid)

# Wait for all three to accept connections
import urllib.request
for name, port, path in [("backend", 8000, "/health"), ("site", 8088, "/"), ("vite", 5173, "/")]:
    for _ in range(40):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=1)
            print(f"{name} ready on {port}")
            break
        except Exception:
            time.sleep(0.5)
    else:
        print(f"WARN: {name} did not come up on {port}")

# Persist PIDs for the stop script
with open(os.path.join(ROOT, "server_pids.txt"), "w") as f:
    for p in procs:
        f.write(f"{p.pid}\n")
print("READY")
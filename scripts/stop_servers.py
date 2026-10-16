"""Kill the servers started by start_servers.py."""
import os, signal, subprocess

ROOT = r"C:\Users\DELL\OneDrive\Documents\Default Project\driftwatch_local"
pidfile = os.path.join(ROOT, "server_pids.txt")
if os.path.exists(pidfile):
    with open(pidfile) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                os.kill(int(line), signal.SIGTERM)
            except (ProcessLookupError, ValueError, OSError):
                pass
# Also kill any lingering uvicorn / vite / server.py on our ports
for pattern in ["uvicorn", "vite", "e2e_site/server.py"]:
    subprocess.run(["taskkill", "/F", "/IM", pattern],
                   capture_output=True)
# Clean up DB
for db in ["e2e_browsers.db"]:
    p = os.path.join(ROOT, db)
    if os.path.exists(p):
        os.remove(p)
        print("removed", db)
print("STOPPED")
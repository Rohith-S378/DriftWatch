"""Wrapper to launch test site and backend, then run E2E test runner."""
import subprocess
import sys
import os

def main():
    db_path = "e2e_test.db"

    # Remove old DB if exists
    if os.path.exists(db_path):
        os.remove(db_path)

    root_cwd = os.getcwd()  # DriftWatch project root
    print(f"Project root: {root_cwd}")

    # Set environment variables
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    env["ALLOW_LOCAL_CRAWLS"] = "True"
    env["WEBHOOK_SECRET"] = "test"
    env["PYTHONPATH"] = root_cwd

    # Start backend and server processes from project root (not scripts folder)
    backend_proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd=root_cwd,
        env=env
    )

    server_proc = subprocess.Popen(
        [sys.executable, "e2e_site/server.py", "8088"],
        cwd=root_cwd
    )

    print("Waiting 7s for servers to stabilize...")
    import time
    time.sleep(7)

    # Run E2E runner with fresh env
    runner_env = os.environ.copy()
    runner_env["DATABASE_URL"] = f"sqlite+aiosqlite:///{db_path}"
    runner_env["ALLOW_LOCAL_CRAWLS"] = "True"
    runner_env["PYTHONPATH"] = root_cwd

    print("Running E2E verification...")
    result = subprocess.run(
        [sys.executable, "scripts/e2e_test_runner.py"],
        cwd=root_cwd,
        env=runner_env
    )

    # Cleanup
    print("Stopping servers...")
    try:
        server_proc.terminate()
        server_proc.wait(timeout=5)
    except:
        server_proc.kill()
    try:
        backend_proc.terminate()
        backend_proc.wait(timeout=5)
    except:
        backend_proc.kill()

    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"Cleaned up {db_path}")

    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
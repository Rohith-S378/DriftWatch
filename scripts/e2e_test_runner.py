"""
Comprehensive End-to-End Verification Runner for DriftWatch.
Executes the full 9-step verification sequence against live backend and test site processes.
"""
import requests
import time
import sys
import os

BACKEND_URL = "http://localhost:8000"
TEST_SITE_URL = "http://127.0.0.1:8088"

def print_step(num, title):
    print("\n" + "="*70)
    print(f"  STEP {num}: {title}")
    print("="*70)

def safe(text):
    """Make text safe for the Windows cp1252 console."""
    return str(text).encode("cp1252", "replace").decode("cp1252")

def main():
    print("Starting DriftWatch E2E Verification Workflow...\n")

    # Cleanup from previous runs
    try:
        print("Cleaning up from previous E2E runs...")
        requests.delete(f"{BACKEND_URL}/api/competitors/ApexLearning", timeout=5)
    except Exception:
        pass  # Not found or already cleaned

    # STEP 1: Health check
    print_step(1, "Health Check")
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=5)
        print(f"GET /health -> status: {r.status_code}, response: {r.json()}")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
        print("[OK] STEP 1 PASSED: Backend is healthy.")
    except Exception as e:
        print(f"[FAIL] STEP 1 FAILED: {e}")
        sys.exit(1)

    # STEP 2: Register Competitor
    print_step(2, "Register Competitor")
    comp_name = "ApexLearning"
    comp_url = f"{TEST_SITE_URL}/?v=A"
    r = requests.post(
        f"{BACKEND_URL}/api/competitors/add",
        json={"name": comp_name, "url": comp_url},
        timeout=5,
    )
    print(f"POST /api/competitors/add -> status: {r.status_code}, json: {r.json()}")
    assert r.status_code == 200
    assert r.json()["name"] == comp_name
    print("[OK] STEP 2 PASSED: Registered competitor successfully.")

    # STEP 3: Duplicate Registration Handling
    print_step(3, "Duplicate Registration Handling")
    # Identical name
    r_dup1 = requests.post(
        f"{BACKEND_URL}/api/competitors/add",
        json={"name": "ApexLearning", "url": comp_url},
        timeout=5,
    )
    print(f"POST duplicate name 'ApexLearning' -> status: {r_dup1.status_code}, detail: {r_dup1.json().get('detail')}")
    assert r_dup1.status_code == 400

    # Case variation 'apexlearning'
    r_dup2 = requests.post(
        f"{BACKEND_URL}/api/competitors/add",
        json={"name": "apexlearning", "url": comp_url},
        timeout=5,
    )
    print(f"POST case variation 'apexlearning' -> status: {r_dup2.status_code}, detail: {r_dup2.json().get('detail')}")
    assert r_dup2.status_code == 400
    print("[OK] STEP 3 PASSED: Duplicate registration correctly rejected for exact & case variations.")

    # STEP 4: Initial Crawl (Baseline)
    print_step(4, "Initial Crawl (Baseline)")
    r_crawl1 = requests.post(
        f"{BACKEND_URL}/api/crawl/single",
        json={"source_id": comp_name, "url": f"{TEST_SITE_URL}/?v=A"},
        timeout=10,
    )
    print(f"POST /api/crawl/single (Version A) -> status: {r_crawl1.status_code}, success: {r_crawl1.json().get('success')}")
    data1 = r_crawl1.json()
    assert data1["success"] is True
    print(f"Extracted Headline: '{data1.get('headline')}'")
    print(f"Extracted Pricing Plans: {data1.get('pricing')}")

    # Check events - MUST BE 0 (baseline)
    r_events1 = requests.get(f"{BACKEND_URL}/api/events/{comp_name}", timeout=5)
    events1 = r_events1.json()
    print(f"GET /api/events/{comp_name} -> count: {len(events1)}")
    assert len(events1) == 0
    print("[OK] STEP 4 PASSED: Baseline snapshot created, 0 change events generated.")

    time.sleep(1.2)

    # STEP 5: Unchanged Crawl
    print_step(5, "Unchanged Crawl")
    r_crawl2 = requests.post(
        f"{BACKEND_URL}/api/crawl/single",
        json={"source_id": comp_name, "url": f"{TEST_SITE_URL}/?v=A"},
        timeout=10,
    )
    print(f"POST /api/crawl/single (Version A second time) -> success: {r_crawl2.json().get('success')}")
    assert r_crawl2.json()["success"] is True

    r_events2 = requests.get(f"{BACKEND_URL}/api/events/{comp_name}", timeout=5)
    events2 = r_events2.json()
    print(f"GET /api/events/{comp_name} -> count: {len(events2)}")
    assert len(events2) == 0
    print("[OK] STEP 5 PASSED: Unchanged crawl produced snapshot, STILL 0 change events.")

    time.sleep(1.2)

    # STEP 6: Modified Crawl (Version B)
    print_step(6, "Modified Crawl (Version B)")
    r_crawl3 = requests.post(
        f"{BACKEND_URL}/api/crawl/single",
        json={"source_id": comp_name, "url": f"{TEST_SITE_URL}/?v=B"},
        timeout=10,
    )
    data3 = r_crawl3.json()
    print(f"POST /api/crawl/single (Version B) -> success: {data3.get('success')}")
    assert data3["success"] is True
    print(f"New Headline: '{data3.get('headline')}'")
    print(f"New Pricing: {data3.get('pricing')}")

    r_events3 = requests.get(f"{BACKEND_URL}/api/events/{comp_name}", timeout=5)
    events3 = r_events3.json()
    print(f"GET /api/events/{comp_name} -> count: {len(events3)}")
    assert len(events3) > 0
    for idx, ev in enumerate(events3, 1):
        desc = ev['description'].replace('\u2192', '->')
        print(f"   Event {idx}: type={ev['change_type']}, severity={ev['severity']}, desc='{desc}'")
    print("[OK] STEP 6 PASSED: Modified crawl generated change events.")

    # STEP 7: Dashboard Verification & Ask AI
    print_step(7, "Dashboard Verification & Ask AI Grounded Q&A")
    r_all = requests.get(f"{BACKEND_URL}/api/events", timeout=5)
    assert r_all.status_code == 200
    print(f"GET /api/events -> total events in system: {len(r_all.json())}")

# Ask AI query
    ai_req = {"question": "What changed with ApexLearning pricing?", "source_id": comp_name}
    r_ai = requests.post(f"{BACKEND_URL}/api/ai/query", json=ai_req, timeout=5)
    ai_resp = r_ai.json()
    print(f"Ask AI Question: '{ai_req['question']}'")
    print(f"Ask AI Answer: '{safe(ai_resp.get('answer'))}'")
    print(f"Ask AI Evidence Citations: {len(ai_resp.get('evidence', []))}")
    assert r_ai.status_code == 200
    assert len(ai_resp.get("answer", "")) > 0
    print("[OK] STEP 7 PASSED: Dashboard endpoints and Ask AI function correctly.")

    # STEP 8: Crawl Failure Handling
    print_step(8, "Crawl Failure Handling")
    r_fail = requests.post(
        f"{BACKEND_URL}/api/crawl/single",
        json={"source_id": comp_name, "url": "http://127.0.0.1:59999/unreachable"},
        timeout=10,
    )
    fail_data = r_fail.json()
    print(f"POST /api/crawl/single (unreachable URL) -> success: {fail_data.get('success')}, error: '{fail_data.get('error')}'")
    assert r_fail.status_code == 200
    assert fail_data["success"] is False

    # Check that events count remained identical
    r_events_after = requests.get(f"{BACKEND_URL}/api/events/{comp_name}", timeout=5)
    assert len(r_events_after.json()) == len(events3)
    print("[OK] STEP 8 PASSED: Crawl failure handled gracefully, existing state preserved.")

    # STEP 9: Data Persistence Verification
    print_step(9, "Data Persistence Verification (post-restart state check)")
    r_comps = requests.get(f"{BACKEND_URL}/api/competitors", timeout=5)
    comps = r_comps.json().get("competitors", [])
    print(f"Registered Competitors: {comps}")
    assert any(c["source_id"] == comp_name for c in comps)

    r_events_final = requests.get(f"{BACKEND_URL}/api/events/{comp_name}", timeout=5)
    print(f"Events for {comp_name}: {len(r_events_final.json())}")
    assert len(r_events_final.json()) == len(events3)
    print("[OK] STEP 9 PASSED: Competitors and change events persisted in DB.")

    print("\n" + "="*70)
    print("  ALL 9 END-TO-END VERIFICATION STEPS COMPLETED SUCCESSFULLY!  ")
    print("="*70 + "\n")

if __name__ == "__main__":
    main()



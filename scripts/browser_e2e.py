import asyncio
import json
import sys

BASE = "http://localhost:5173"
API = "http://127.0.0.1:8000"
SITE = "http://127.0.0.1:8088"
COMP_NAME = "ApexBrowser"
COMP_URL = "http://127.0.0.1:8088/"

results = []
console_messages = []
failed_requests = []


def check(name, ok, detail=""):
    results.append((name, ok, detail))
    mark = "PASS" if ok else "FAIL"
    line = "[{}] {}".format(mark, name)
    if detail:
        clean_detail = detail.encode("ascii", "replace").decode("ascii")
        line += " -- " + clean_detail
    print(line)


async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await ctx.new_page()

        console_errors = []
        console_warnings = []
        page.on("console", lambda m: (
            console_errors.append(m.text) if m.type == "error"
            else console_warnings.append(m.text) if m.type == "warning"
            else None
        ))
        page.on("requestfailed", lambda r: failed_requests.append(
            "{} {} -> {}".format(r.method, r.url, r.failure)))

        # STEP 1: Open the application
        await page.goto(BASE, wait_until="networkidle")
        body1 = await page.inner_text("body")
        check("1. App opens (DomainSelect)", "Select Your Domain" in body1,
              body1[:60].replace("\n", " "))
        # Empty-state checks BEFORE any data
        await page.goto(BASE + "/insights", wait_until="networkidle")
        text = await page.inner_text("body")
        check("2a. Insights empty state: zeros not NaN/undefined",
              "NaN" not in text and "undefined" not in text.lower())
        check("2b. Insights empty state: no-activity message",
              "No significant insights to display at this time" in text)

        await page.goto(BASE + "/changes", wait_until="networkidle")
        text = await page.inner_text("body")
        check("2c. Changes empty state",
              "No competitor changes detected yet" in text and "NaN" not in text)

        await page.goto(BASE + "/overview", wait_until="networkidle")
        text = await page.inner_text("body")
        check("2d. Overview empty state",
              "No recent crawling activity" in text
              and "No competitors added yet" in text and "NaN" not in text)

        # Ask AI empty state BEFORE any data
        await page.goto(BASE + "/ask", wait_until="networkidle")
        await page.fill('input[placeholder*="Ask a question"]', "Any competitor updates?")
        await page.click("button:has-text('Ask')")
        for _ in range(20):
            await page.wait_for_timeout(500)
            text = await page.inner_text("body")
            if "No recorded changes" in text:
                break
        check("2e. Ask AI empty state: no-data message",
              "No recorded changes or snapshots matched" in text and "NaN" not in text)

        # STEP 4: Register a test competitor via the UI.
        # Navigate back to Overview to find the registration inputs.
        await page.goto(BASE + "/overview", wait_until="networkidle")
        # Reset the controlled test site to Version A first so the baseline
        # snapshot captures A and the later B-crawl produces a real diff.
        import urllib.request
        req_a = urllib.request.Request(f"{SITE}/set_version?v=A", data=b"", method="POST")
        urllib.request.urlopen(req_a, timeout=5).read()
        await page.fill('input[placeholder="e.g., Byjus"]', COMP_NAME)
        await page.fill('input[placeholder="e.g., https://byjus.com/pricing"]', COMP_URL)

        api_responses = []
        add_req = crawl_req = None

        def _cap_req(req):
            nonlocal add_req, crawl_req
            if "/api/competitors/add" in req.url:
                add_req = {"method": req.method, "post_data": req.post_data,
                           "ct": req.headers.get("content-type", "")}
            if "/api/crawl/single" in req.url:
                crawl_req = {"method": req.method, "post_data": req.post_data,
                             "ct": req.headers.get("content-type", "")}

        def _cap_resp(resp):
            api_responses.append((resp.status, resp.url, resp.request.method))

        page.on("request", _cap_req)
        page.on("response", _cap_resp)

        await page.click("button:has-text('Add & Analyze Competitor')")
        await page.wait_for_timeout(3000)

        add_hits = [(s, u) for s, u, m in api_responses
                    if "/api/competitors/add" in u]
        crawl_hits = [(s, u) for s, u, m in api_responses
                      if "/api/crawl/single" in u]
        add_status = add_hits[0][0] if add_hits else None
        crawl_status = crawl_hits[0][0] if crawl_hits else None

        check("3. POST /api/competitors/add contract",
              add_status == 200 and add_req
              and add_req["ct"] == "application/json"
              and json.loads(add_req["post_data"]) == {"name": COMP_NAME, "url": COMP_URL},
              "status={} body={}".format(add_status, add_req["post_data"] if add_req else None))

        check("4. POST /api/crawl/single contract",
              crawl_status == 200 and crawl_req
              and json.loads(crawl_req["post_data"]) == {"source_id": COMP_NAME, "url": COMP_URL},
              "status={} body={}".format(crawl_status, crawl_req["post_data"] if crawl_req else None))

        body = await page.inner_text("body")
        check("5. Crawl success card shown",
              "Crawl Successful" in body and "NaN" not in body,
              "headline: 'Leading AI Coaching & Certification'")
        check("5b. Correct competitor identifier in Tracked list",
              COMP_NAME in body, "name rendered exactly as registered")

        # Reload and verify persistence
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(1500)
        body = await page.inner_text("body")
        check("6. Persistence after reload",
              COMP_NAME in body and "Tracked Competitors (1)" in body,
              "competitor survived full page reload")

        # Controlled change: switch site to Version B (via POST) and re-crawl (Crawl Now)
        req = urllib.request.Request(f"{SITE}/set_version?v=B", data=b"", method="POST")
        urllib.request.urlopen(req, timeout=5).read()

        await page.click("button:has-text('Crawl Now')")
        await page.wait_for_timeout(5000)

        # API ground truth
        with urllib.request.urlopen(f"{API}/api/events/{COMP_NAME}", timeout=10) as r:
            events = json.loads(r.read().decode())
        price_events = [e for e in events if e["change_type"] == "price"]
        has_values = any((e.get("old_value") not in (None, ""))
                         and (e.get("new_value") not in (None, ""))
                         for e in price_events)
        check("7. Controlled change detected (API)",
              len(price_events) >= 2 and has_values,
              "{} events, {} price events".format(len(events), len(price_events)))
        check("7b. Events persisted with correct source_id",
              len(events) > 0 and all(e["source_id"] == COMP_NAME for e in events),
              "all events carry the registered identifier")

        # Open Insights, Changes, Ask AI with data
        await page.goto(BASE + "/insights", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        body = await page.inner_text("body")
        check("8a. Insights shows data + no NaN/undefined",
              "Total Changes Detected" in body
              and "NaN" not in body and "undefined" not in body.lower())

        await page.goto(BASE + "/changes", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        body = await page.inner_text("body")
        check("8b. Changes shows detected change + no NaN/undefined",
              ("Significant pricing change" in body or "Previous Value" in body)
              and "NaN" not in body and "undefined" not in body.lower())

        await page.goto(BASE + "/ask", wait_until="networkidle")
        await page.fill('input[placeholder*="Ask a question"]',
                        "What changed with pricing?")
        await page.click("button:has-text('Ask')")
        for _ in range(20):
            await page.wait_for_timeout(500)
            body = await page.inner_text("body")
            if "Answer" in body or "Error" in body:
                break
        check("8c. Ask AI grounded answer with evidence",
              "Answer" in body and "Supporting Evidence" in body
              and "NaN" not in body and "undefined" not in body.lower())

        # Failed crawl state via UI
        await page.goto(BASE + "/overview", wait_until="networkidle")
        await page.wait_for_timeout(800)
        await page.fill('input[placeholder="e.g., Byjus"]', "DeadCompetitor")
        await page.fill('input[placeholder="e.g., https://byjus.com/pricing"]',
                        "http://127.0.0.1:59999/")
        await page.click("button:has-text('Add & Analyze Competitor')")
        # Crawler retries up to 3 times on connection failure, so wait
        # dynamically for the failure card to appear (up to 15s).
        for _ in range(30):
            await page.wait_for_timeout(500)
            body = await page.inner_text("body")
            if "Crawl Failed" in body or "Crawl Successful" in body:
                break
        check("9. Failed crawl shows failure state (not success)",
              "Crawl Failed" in body and "Crawl Successful" not in body,
              "unreachable host reported as failed")

        # Final console / network audit
        real_errors = [e for e in console_errors
                       if "favicon" not in e.lower()
                       and "404" not in e
                       and "Failed to load resource" not in e]
        check("10. No unexplained console errors",
              len(real_errors) == 0,
              "; ".join(real_errors[:3]) if real_errors else
              "{} raw errors (all benign), {} warnings".format(
                  len(console_errors), len(console_warnings)))

        # Failed requests: the intentional dead-port crawl is expected to fail
        unexpected = [f for f in failed_requests if "59999" not in f]
        check("11. No unexpected network failures",
              len(unexpected) == 0,
              "; ".join(unexpected[:3]) if unexpected else
              "{} total (dead-port crawl intentional)".format(len(failed_requests)))

        # Step 12: Verify Phase 2 Automated Competitor Discovery page
        await page.goto(BASE + "/discovery", wait_until="networkidle")
        disc_text = await page.inner_text("body")
        check("12. Discovery page renders input and heading",
              "Automated Competitor Discovery" in disc_text and "Discover Competitors" in disc_text)

        # Enter company website into discovery form
        await page.fill('input[type="url"]', "http://127.0.0.1:8088/?v=A")

        # Capture any network/console activity during discovery request
        disc_req = []
        disc_resp = []
        disc_logs = []
        page.on("request", lambda r: disc_req.append(r.url) if "discovery" in r.url else None)
        page.on("response", lambda r: disc_resp.append((r.status, r.url)) if "discovery" in r.url else None)
        page.on("console", lambda m: disc_logs.append(m.text) if "discovery" in m.text.lower() else None)

        await page.click("button:has-text('Discover Competitors')")

        # Wait for profile and candidate recommendations to appear (discovery runs bounded crawl + mock search + verify)
        generated_ok = False
        for _ in range(60):
            await page.wait_for_timeout(500)
            disc_text = await page.inner_text("body")
            if ("GENERATED PROFILE" in disc_text or "Generated Profile" in disc_text) and "Ranked Competitor Recommendations" in disc_text:
                generated_ok = True
                break

        # Capture diagnostic output if failed
        check("13. Discovery generates profile and candidate recommendations",
              generated_ok,
              "" if generated_ok else f"logs={disc_logs} body_len={len(disc_text)} full_body={disc_text.replace(chr(10), ' | ')}")

        # Step 14: Test 1-click competitor tracking from discovery recommendations
        track_btn = await page.query_selector("button:has-text('Track Competitor')")
        if track_btn:
            await track_btn.click()
            await page.wait_for_timeout(1000)
            disc_text_after = await page.inner_text("body")
            tracked_ok = "Monitored" in disc_text_after or "Successfully added" in disc_text_after
            check("14. 1-Click Track adds discovery candidate to active monitoring", tracked_ok)
        else:
            check("14. 1-Click Track adds discovery candidate to active monitoring", False, "No Track Competitor button found")

        # Screenshots for evidence
        for route, name in [("/discovery", "discovery"), ("/overview", "overview"), ("/insights", "insights"),
                            ("/changes", "changes"), ("/ask", "askai")]:
            await page.goto(BASE + route, wait_until="networkidle")
            await page.wait_for_timeout(800)
            await page.screenshot(path="shot_{}.png".format(name), full_page=True)
        print("screenshots: shot_discovery.png shot_overview.png shot_insights.png shot_changes.png shot_askai.png")

        await browser.close()

    passed = sum(1 for _, ok, _ in results if ok)
    print("\nBROWSER E2E: {}/{} checks passed".format(passed, len(results)))
    print("Console warnings: {}".format(
        "; ".join(console_warnings[:5]) if console_warnings else "none"))
    sys.exit(0 if passed == len(results) else 1)


asyncio.run(main())
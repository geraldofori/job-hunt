"""Approval-queue runner — for jobs apply_engine can't auto-submit
(external portals: Greenhouse/Lever/Workday/StepStone/...) and for
jobs needing a voice-written cover letter.

Run in a session with Gerald (headful browser):

  venv/bin/python scripts/apply_queue.py             # process all queued
  venv/bin/python scripts/apply_queue.py --limit 3   # first 3 only

For each job:
  1. If cover_letters/<job id>.pdf missing, remind Gerald to let the agent write it.
  2. Opens the portal in the persistent browser profile (all logins/cookies available).
  3. Uploads CV (+ cover letter if present) into any visible file inputs,
     fills obvious text fields from profile.yaml.
  4. Leaves the FINAL SUBMIT click to the human. Watches for it (up to 10 min),
     then records status in the tracker.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

from apply_engine import human_pause, register_account, resolve_profile_value
from common import ROOT, db, find_cover_letter, get_logger, load_config

log = get_logger("queue")


def next_queued(conn, limit: int):
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status='shortlisted' AND site != 'linkedin' "
        "ORDER BY score DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


def cover_letter_path(job_id: str, company: str = "", role: str = "") -> Path | None:
    _, pdf = find_cover_letter(job_id, company, role)
    return pdf


CLOSED_PATTERNS = (
    r"no longer accepting applications", r"no longer accepting",
    r"this job is no longer available", r"job (is )?(closed|expired)",
    r"(position|role) (is )?(closed|no longer available|has been filled)",
    r"applications? (are|is) closed",
    r"stellenanzeige (ist )?(nicht mehr|geschlossen)",
    r"bewerbungen? (sind|ist) (nicht mehr|geschlossen)",
    r"keine neuen bewerbungen", r"diese stelle ist nicht mehr",
    r"job opening (has )?closed", r"vacancy is closed",
)


def looks_closed(page) -> bool:
    """Cheap check for expired postings so we skip them instead of stalling."""
    try:
        body = (page.evaluate("() => (document.body.innerText || '').slice(0, 2500)") or "")
    except Exception:
        return False
    return any(re.search(p, body, re.I) for p in CLOSED_PATTERNS)


def process(page, job: dict, profile: dict) -> str:
    url = job["job_url"]
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    human_pause(2, 4)

    if looks_closed(page):
        print(f">>> SKIPPED (closed): {job['title']} @ {job['company']}")
        return "closed"

    # upload CV (+ cover letter if the agent wrote one)
    cv = str(ROOT / profile["documents"]["cv_pdf"])
    cl = cover_letter_path(job["id"], job.get("company") or "", job.get("title") or "")
    uploads = page.locator("input[type='file']")
    for i in range(min(uploads.count(), 4)):
        el = uploads.nth(i)
        try:
            if cl and i == 1:
                el.set_input_files(str(cl))
            else:
                el.set_input_files(cv)
        except Exception as e:
            log.debug("upload skip: %s", e)

    # naive text-field fill on common ATS patterns
    for pat, key in [("name", "full_name"), ("email", "email"),
                     ("phone", "phone"), ("resume", None), ("cover", None)]:
        for el in page.locator(f"input[name*='{pat}' i], textarea[name*='{pat}' i]"):
            try:
                if not el.is_visible() or el.input_value().strip():
                    continue
                if el.get_attribute("type") in ("file", "checkbox", "radio", "submit"):
                    continue
                val = resolve_profile_value(profile, key) if key else ""
                if val:
                    el.fill(val)
            except Exception:
                continue

    print(f"\n>>> OPEN FOR REVIEW: {job['title']} @ {job['company']}")
    print(f"    {url}")
    if not cl:
        print(f"    (no cover letter yet — ask the agent: job id {job['id']})")
    input("    Submit manually in the browser window, then press Enter here... ")
    return "applied"


def main() -> None:
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 10
    profile = load_config("profile.yaml")
    conn = db()
    jobs = next_queued(conn, limit)
    if not jobs:
        print("Queue empty — everything is applied or LinkedIn-auto jobs only.")
        return
    from common import BROWSER_PROFILE
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE), headless=False,
            viewport={"width": 1360, "height": 900})
        page = ctx.new_page()
        for job in jobs:
            try:
                result = process(page, job, profile)
            except Exception as e:
                log.error("queue job failed: %s", e)
                result = "failed"
            if result == "applied":
                conn.execute(
                    "UPDATE jobs SET status='applied', applied_at=? WHERE id=?",
                    (datetime.now().isoformat(timespec="seconds"), job["id"]))
                try:
                    from tracker import add_application
                    add_application(job, status="Applied")
                except SystemExit:
                    from daily import track_application
                    track_application(job, "Applied")
            elif result == "closed":
                conn.execute("UPDATE jobs SET status='closed' WHERE id=?", (job["id"],))
                conn.commit()
        ctx.close()
    conn.commit()


if __name__ == "__main__":
    main()

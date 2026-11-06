"""Supervised single application — the safe way to fire the first ones.

Usage (headful, you watch the browser):
  venv/bin/python scripts/apply_one.py <job_id> [--submit]

Flow: opens the job, walks the Easy Apply form (or opens the portal),
pauses at the review step with a screenshot + summary of what was filled.
Submits only if you pass --submit (and it reached review cleanly) or press
Enter at the prompt when satisfied.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

from common import ROOT, db, find_cover_letter, get_logger, load_config

log = get_logger("apply_one")


def main() -> None:
    job_id = sys.argv[1] if len(sys.argv) > 1 else ""
    force_submit = "--submit" in sys.argv
    conn = db()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        sys.exit(f"job id {job_id!r} not found")
    job = dict(row)

    profile = load_config("profile.yaml")
    resume_pdf = ROOT / profile["documents"]["cv_pdf"]
    cover_md, cover_pdf = find_cover_letter(job_id, job.get("company") or "", job.get("title") or "")
    cover_text = cover_md.read_text() if cover_md and cover_md.exists() else None
    if cover_pdf:
        print(f"cover letter: {cover_pdf.name}")
    else:
        print("cover letter: none on file (write one if the posting asks for it)")

    from playwright.sync_api import sync_playwright
    from apply_engine import LinkedInEasyApply, screenshot, human_pause
    from common import BROWSER_PROFILE

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            user_data_dir=str(BROWSER_PROFILE), headless=False,
            viewport={"width": 1360, "height": 900})
        page = ctx.new_page()
        url = job["job_url"]
        if job["site"] == "linkedin" or "linkedin.com" in url:
            engine = LinkedInEasyApply(
                page, profile, resume_pdf,
                cover_pdf if cover_pdf and cover_pdf.exists() else None,
                cover_text, auto_submit=force_submit,
                keep_open_on_abort=not force_submit)
            print(f"Opening {job['title']} @ {job['company']} — watch the browser...")
            result = engine.run(url)
            print("engine result:", result)
            print("unknown questions:", engine.unknown_questions or "none")
            shot = screenshot(page, f"{job_id}_review")
            print(f"screenshot: {shot}")
            if result == "closed":
                conn.execute(
                    "UPDATE jobs SET status='closed' WHERE id=?", (job_id,))
                conn.commit()
                print("Posting closed / no longer accepting applications — marked and skipped.")
            elif result == "not_easy_apply":
                conn.execute(
                    "UPDATE jobs SET status='external' WHERE id=?", (job_id,))
                conn.commit()
                print("Not an Easy Apply posting — left for the external-portal queue.")
            elif result == "needs_manual":
                print("Aborted before submit — questions it could not answer safely.")
                print("Browser stays open with the draft untouched. Fix it by hand and")
                print("submit; this window watches for the confirmation (max 10 min).")
                submitted = False
                deadline = time.time() + 600
                while time.time() < deadline:
                    try:
                        submitted = bool(page.evaluate("""() => {
                            const t = (document.body.innerText || '').toLowerCase();
                            return /application submitted|bewerbung wurde "
                                   ".*(gesendet|übermittelt)|you are applied|"
                                   "application sent/.test(t);
                        }"""))
                    except Exception:
                        pass
                    if submitted:
                        break
                    time.sleep(3)
                if submitted:
                    conn.execute(
                        "UPDATE jobs SET status='applied', applied_at=? WHERE id=?",
                        (datetime.now().isoformat(timespec="seconds"), job_id))
                    conn.commit()
                    from tracker import add_application
                    add_application({**job, "notes": "completed manually after engine abort"})
                    print("Detected submission — recorded as applied.")
                else:
                    print("No submission detected — left as shortlisted for a rerun.")
            elif result in ("ready_to_submit", "failed") and "linkedin.com" in page.url:
                if force_submit:
                    btn = page.locator(
                        "button:has-text('Submit application'),"
                        "button:has-text('Bewerbung absenden')").first
                    if btn.count() and btn.is_visible():
                        btn.click()
                        human_pause(2, 4)
                        print("SUBMITTED")
                        result = "applied"
                    else:
                        print("No submit button visible — inspect the browser window.")
                else:
                    try:
                        ans = input("Submit now? [y/N] ")
                    except EOFError:
                        ans = "n"
                    if ans.lower() == "y":
                        btn = page.locator(
                            "button:has-text('Submit application'),"
                            "button:has-text('Bewerbung absenden')").first
                        if btn.count() and btn.is_visible():
                            btn.click()
                            human_pause(2, 4)
                            print("SUBMITTED")
                            result = "applied"
        else:
            page.goto(url, wait_until="domcontentloaded")
            print(f"Portal opened for manual handling: {url}")
            result = input("Did you submit successfully? [y/N] ") == "y" and "applied" or "skipped"

        if result == "applied":
            conn.execute(
                "UPDATE jobs SET status='applied', applied_at=? WHERE id=?",
                (datetime.now().isoformat(timespec="seconds"), job_id))
            conn.commit()
            from tracker import add_application
            add_application({**job, "notes": f"applied via {Path(url).host}"},
                            cover_letter=str(cover_pdf) if cover_pdf.exists() else "",
                            status="Applied")
            print("Tracked in Google Sheets.")
        ctx.close()


if __name__ == "__main__":
    main()

"""Daily orchestrator: discover -> match -> apply/queue -> track -> monitor -> brief.

Designed to run unattended (launchd). Degrades gracefully:
- Google not set up yet -> applications recorded to local CSV fallback + queue file.
- LinkedIn not signed in -> jobs go to the approval queue instead of failing.

Usage:
  venv/bin/python scripts/daily.py            # full run
  venv/bin/python scripts/daily.py --no-apply # discovery + matching + prep only
  venv/bin/python scripts/daily.py --test     # reduced discovery for smoke tests
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

from common import DATA, ROOT, db, get_logger, load_config
from match import job_passes_filters, score_job

log = get_logger("daily")
FALLBACK_CSV = DATA / "applications_local.csv"
QUEUE_FILE = DATA / "approval_queue.md"


def pick_shortlisted(cfg: dict, limit: int) -> list[dict]:
    """Best in-scope jobs still waiting, re-filtered and re-scored.

    The DB backlog can contain jobs discovered before a filter change (e.g. a
    marketing role from an earlier run), so filters are re-applied here instead
    of trusting whatever is still flagged shortlisted.
    """
    profile = load_config("profile.yaml")
    rows = db().execute(
        "SELECT * FROM jobs WHERE status='shortlisted'").fetchall()
    out: list[dict] = []
    for r in rows:
        job = dict(r)
        ok, _reason = job_passes_filters(job, cfg)
        if not ok:
            continue
        job["score"] = score_job(job, cfg, profile)
        out.append(job)
    out.sort(key=lambda j: (j["score"], j.get("date_posted") or ""), reverse=True)
    return out[:limit]


def is_signed_in(page, site: str) -> bool:
    import re
    if site == "linkedin":
        page.goto("https://www.linkedin.com/me", wait_until="domcontentloaded")
        return not re.search(r"checkpoint|login|authwall", page.url)
    return True


def main() -> int:
    args = sys.argv[1:]
    do_apply = "--no-apply" not in args
    test = "--test" in args
    cfg = load_config("search.yaml")
    daily = cfg["daily"]
    started = datetime.now()

    # 1) discover + match
    import discover
    import match
    flag = Path(ROOT) / "scripts" / ".test-mode"
    if test:
        flag.write_text("1")
    else:
        flag.unlink(missing_ok=True)
    discover.main()
    match.main()

    # 1b) enrich shortlisted jobs with full JDs (for cover letters)
    import describe
    describe.main()

    # 2) shortlist
    jobs = pick_shortlisted(cfg, daily["max_applications"] * 3)
    easy = [j for j in jobs if j["site"] == "linkedin" and j.get("easy_apply")][: daily["max_applications"]]
    queued = [j for j in jobs if j not in easy][: daily["max_applications"]]
    log.info("Shortlist: %d total, %d linkedin-easy candidates, %d queued",
             len(jobs), len(easy), len(queued))

    # 3) apply (LinkedIn Easy Apply only, unattended)
    applied, manual = [], []
    if do_apply and easy:
        from apply_engine import apply_to_job
        profile = load_config("profile.yaml")
        resume_pdf = ROOT / profile["documents"]["cv_pdf"]
        from playwright.sync_api import sync_playwright
        from common import BROWSER_PROFILE
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(BROWSER_PROFILE), headless=False,
                viewport={"width": 1360, "height": 900})
            page = ctx.new_page()
            from apply_engine import LinkedInEasyApply, human_pause
            if not is_signed_in(page, "linkedin"):
                log.warning("LinkedIn not signed in — everything goes to queue.")
                easy, queued = [], jobs[: daily["max_applications"]]
            for j in easy[: daily["max_applications"]]:
                engine = LinkedInEasyApply(
                    page, profile, resume_pdf, None, None,
                    auto_submit=daily["easy_apply_auto_submit"])
                try:
                    result = engine.run(j["job_url"])
                except Exception as e:
                    log.error("engine crash on %s: %s", j["id"], str(e)[:80])
                    result = "failed"
                conn = db()
                if result == "applied":
                    conn.execute("UPDATE jobs SET status='applied', applied_at=datetime('now') WHERE id=?", (j["id"],))
                    track_application(j, "Applied")
                    applied.append(j)
                elif result in ("needs_manual", "not_easy_apply", "portal_opened", "ready_to_submit"):
                    conn.execute("UPDATE jobs SET status='shortlisted', notes=COALESCE(notes,'')||' | needs manual' WHERE id=?", (j["id"],))
                    manual.append(j)
                    queued.append(j)
                human_pause(daily["pace_seconds_min"], daily["pace_seconds_max"])
            conn.commit()
            ctx.close()

    # 4) approval queue file (external portals — agent/Gerald handle in session)
    if queued:
        lines = [f"# Approval queue — {started:%Y-%m-%d %H:%M}", ""]
        for j in queued:
            lines.append(f"- [{j['score'] or 0:.1f}] **{j['title']}** @ {j['company']} "
                         f"({j['location']}, {j['work_model']}, {j['language']}) {j['job_url']}")
        QUEUE_FILE.write_text("\n".join(lines))

    # 5) gmail monitor (skip silently if not set up)
    try:
        import gmail_monitor
        gmail_monitor.main()
    except SystemExit as e:
        log.warning("Gmail/tracker not set up yet: %s", e)

    # 6) daily brief
    brief = DATA / "runs" / f"{started:%Y-%m-%d}_brief.md"
    brief.parent.mkdir(exist_ok=True)
    brief.write_text(
        f"# Daily brief {started:%Y-%m-%d %H:%M}\n\n"
        f"- Auto-applied (LinkedIn Easy Apply): {len(applied)}\n"
        f"- Needs manual/portal approval: {len(queued)}\n"
        f"- Shortlist total: {len(jobs)}\n\n"
        f"Applied:\n" + "\n".join(f"- {j['title']} @ {j['company']}" for j in applied) + "\n\n"
        f"Queue file: data/approval_queue.md\n")
    print(f"\nBRIEF: {len(applied)} applied, {len(queued)} queued for approval -> {brief}")

    # 7) notification
    import subprocess
    subprocess.run([
        "osascript", "-e",
        f'display notification "{len(applied)} applied, {len(queued)} need approval" '
        'with title "Daily job hunt done"'], check=False)
    return len(applied)


def track_application(job: dict, status: str) -> None:
    """Google Sheets if configured, local CSV fallback otherwise."""
    try:
        from tracker import add_application
        add_application(job, status=status)
    except SystemExit:
        exists = FALLBACK_CSV.exists()
        with open(FALLBACK_CSV, "a", newline="") as f:
            w = csv.writer(f)
            if not exists:
                w.writerow(["Date", "Company", "Role", "Platform", "Location",
                            "Work Model", "URL", "Language", "Status", "Notes"])
            w.writerow([f"{datetime.now():%Y-%m-%d}", job["company"], job["title"],
                        job["site"], job["location"], job["work_model"],
                        job["job_url"], job["language"], status, ""])
        log.info("Tracked locally (Google not set up): %s @ %s", job["title"], job["company"])


if __name__ == "__main__":
    sys.exit(0 if main() >= 0 else 1)

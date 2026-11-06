"""Discover Werkstudent jobs from JobSpy (Indeed/LinkedIn/Google) + workingstudentjobs.de.

Each source is wrapped in try/except — a failing source never kills the run.
New jobs are inserted into SQLite with status='new'; dedupe by (site, url).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from common import db, get_logger, job_key, load_config

log = get_logger("discover")


# ---------------------------------------------------------------- JobSpy
def test_mode() -> bool:
    return (Path(__file__).resolve().parent / ".test-mode").exists()


def from_jobspy(cfg: dict) -> Iterable[dict]:
    from jobspy import scrape_jobs

    js = cfg["jobspy"]
    queries = cfg["queries"]["frontend"] + cfg["queries"]["embedded"]
    if test_mode():
        queries = queries[:2]
    sites = []
    if cfg["sources"].get("indeed"):
        sites.append("indeed")
    if cfg["sources"].get("linkedin"):
        sites.append("linkedin")
    if cfg["sources"].get("google_jobs"):
        sites.append("google")
    if not sites:
        return

    search_plans = []
    onsite = (["Chemnitz"] if test_mode() else cfg["locations"]["onsite"])
    for city in onsite:
        for q in queries:
            search_plans.append((q, city))
    for q in queries:  # Germany-wide for remote
        search_plans.append((q, cfg["locations"]["remote"]))

    for q, loc in search_plans:
        try:
            df = scrape_jobs(
                site_name=sites,
                search_term=q,
                google_search_term=f"{q} jobs in {loc}, Germany",
                location=loc,
                country_indeed=js["country_indeed"],
                results_wanted=js["results_wanted_per_query"],
                hours_old=js["hours_old"],
                linkedin_fetch_description=False,
                verbose=False,
            )
        except Exception as e:
            log.warning("JobSpy failed for %r in %r: %s", q, loc, e)
            continue
        if df is None or df.empty:
            continue
        for _, r in df.iterrows():
            def clean(v):
                s = str(v) if v is not None else ""
                return "" if s.lower() in ("nan", "none", "") else s
            yield {
                "site": clean(r.get("site")) or "unknown",
                "title": clean(r.get("title")).strip(),
                "company": clean(r.get("company")).strip(),
                "location": clean(r.get("location")).strip(),
                "job_url": clean(r.get("job_url")).strip(),
                "description": clean(r.get("description"))[:15000],
                "date_posted": clean(r.get("date_posted")),
                "is_remote": bool(r.get("is_remote")) if r.get("is_remote") is not None else None,
                "easy_apply": bool(r.get("easy_apply")),
            }
        log.info("JobSpy %r/%s -> %d rows", q, loc, len(df))


# ------------------------------------------- workingstudentjobs.de (Playwright)
WSJ_CARDS = """() => [...document.querySelectorAll('article')].map(a => {
    const link = [...a.querySelectorAll('a')].find(x => /\\/jobs\\//.test(x.href) && !x.href.includes('/go'));
    return {href: link ? link.href : null, text: a.innerText.replace(/\\n+/g, ' | ')};
})"""


def parse_wsj_card(lines: list[str], fallback_url: str, city: str) -> dict | None:
    """Card text: title | company | [Promoted] | type | posted | location | model | View | skills..."""
    if len(lines) < 6 or "job" not in (fallback_url or ""):
        return None
    def field(match_re):
        for l in lines:
            if match_re.search(l):
                return l
        return ""
    import re as _re
    title = lines[0]
    company = lines[1] if len(lines) > 1 else ""
    if title.lower() in ("promoted",) or "promoted" in title.lower() and len(title) < 12:
        return None
    emp_type = field(_re.compile(r"working student|internship|praktikum|werkstudent", _re.I))
    if not emp_type:
        return None
    loc = field(_re.compile(r"remote|hybrid|onsite|on-site", _re.I))
    city_field = ""
    for l in lines:
        if l.strip() in ("Remote", "Hybrid", "Onsite", "On-site"):
            break
        city_field = l  # last field before work model = location
    work_model = "remote" if "remote" in loc.lower() else \
                 "hybrid" if "hybrid" in loc.lower() else "onsite"
    return {
        "site": "workingstudentjobs",
        "title": title,
        "company": company,
        "location": city_field or city or "Germany",
        "job_url": fallback_url.split("?")[0],
        "description": " | ".join(lines)[:15000],
        "date_posted": "",
        "is_remote": work_model == "remote",
    }


def from_workingstudentjobs(cfg: dict) -> Iterable[dict]:
    """Render the public search pages (allowed by robots.txt; /api and /go
    are disallowed, so we only read listing cards and job detail links)."""
    from playwright.sync_api import sync_playwright

    queries = ["software", "frontend", "embedded", "react", "it"]
    if test_mode():
        queries = queries[:2]
    plans = []
    onsite = (["Chemnitz"] if test_mode() else cfg["locations"]["onsite"])
    for city in onsite:  # per-city pages are reliable
        plans.append((None, f"https://www.workingstudentjobs.de/jobs/in/{city.lower()}"))
    for q in queries:  # global relevance search (catches remote roles)
        plans.append((q, f"https://www.workingstudentjobs.de/?q={q}"))

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
        for q, url in plans:
            city = ""
            if "/jobs/in/" in url:
                city = url.rsplit("/", 1)[-1].capitalize()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                try:
                    page.wait_for_selector("article", timeout=12000)
                except Exception:
                    pass
                page.wait_for_timeout(1500)
            except Exception as e:
                log.warning("wsj.de load failed %s: %s", url, e)
                continue
            cards = page.evaluate(WSJ_CARDS)
            got = 0
            for c in cards:
                job = parse_wsj_card([l.strip() for l in (c.get("text") or "").split("|")],
                                     c.get("href") or "", city)
                if job:
                    yield job
                    got += 1
            log.info("wsj.de %s -> %d cards kept", url, got)
        browser.close()


# ------------------------------------------------------------------- main
def main() -> int:
    cfg = load_config("search.yaml")
    conn = db()
    seen_urls = {r["id"] for r in conn.execute("SELECT id FROM jobs")}
    new_count = 0

    sources = [from_jobspy]
    if cfg["sources"].get("workingstudentjobs_de"):
        sources.append(from_workingstudentjobs)

    for source in sources:
        for job in source(cfg):
            if not job.get("job_url") or not job.get("title"):
                continue
            jid = job_key(job["site"], job["job_url"])
            if jid in seen_urls:
                continue
            conn.execute(
                """INSERT INTO jobs (id, site, title, company, location, job_url,
                                     description, date_posted, work_model, easy_apply)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    jid,
                    job["site"],
                    job["title"],
                    job.get("company", ""),
                    job.get("location", ""),
                    job["job_url"],
                    job.get("description", ""),
                    job.get("date_posted", ""),
                    "remote" if job.get("is_remote") else "unknown",
                    1 if job.get("easy_apply") else 0,
                ),
            )
            seen_urls.add(jid)
            new_count += 1
    conn.commit()
    log.info("Discovery complete: %d new jobs", new_count)
    print(f"NEW_JOBS={new_count}")
    return new_count


if __name__ == "__main__":
    main()

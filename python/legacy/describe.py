"""Enrich shortlisted jobs with full descriptions (for cover letters & QA).

workingstudentjobs.de: fetch the public /jobs/<slug> page via curl (Cloudflare
403s urllib and Next.js hydration strips the JSON-LD from the live DOM, but the
raw HTML has it) and parse the JobPosting JSON-LD.
Indeed/LinkedIn rows usually arrive with a description from JobSpy already.
"""
from __future__ import annotations

import json
import re
import subprocess
import time

from common import db, get_logger

log = get_logger("describe")


def fetch_jsonld(url: str) -> dict | None:
    try:
        html = subprocess.run(
            ["curl", "-s", "-m", "20", url,
             "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"],
            capture_output=True, text=True, check=True).stdout
    except Exception as e:
        log.warning("fetch failed %s: %s", url, e)
        return None
    for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            d = json.loads(m)
        except Exception:
            continue
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            return d
    return None


def main() -> None:
    conn = db()
    rows = conn.execute(
        "SELECT id, job_url, description FROM jobs "
        "WHERE status='shortlisted' AND length(COALESCE(description,'')) < 400 "
        "AND job_url LIKE '%workingstudentjobs.de/jobs/%'"
    ).fetchall()
    if not rows:
        log.info("Nothing to enrich.")
        print("ENRICHED=0")
        return

    enriched = 0
    for r in rows:
        time.sleep(0.8)  # be polite
        d = fetch_jsonld(r["job_url"])
        if not d:
            continue
        desc = re.sub("<[^>]+>", " ", d.get("description", ""))
        desc = re.sub(r"\s+", " ", desc)[:15000]
        remote = d.get("jobLocationType", "") == "TELECOMMUTE"
        conn.execute(
            "UPDATE jobs SET description=?, "
            "work_model=CASE WHEN ? THEN 'remote' ELSE work_model END WHERE id=?",
            (desc, remote, r["id"]))
        enriched += 1
    conn.commit()
    log.info("Enriched %d/%d descriptions", enriched, len(rows))
    print(f"ENRICHED={enriched}")


if __name__ == "__main__":
    main()

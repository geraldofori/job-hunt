"""Bridge CLI: fetch jobs via python-jobspy, emit JSON lines to stdout.

Usage: jobspy_fetch.py '<json-config>'
Config shape:
{
  "queries": ["Werkstudent Frontend", ...],
  "location": "Germany",
  "hours_old": 168,
  "results_per_query": 25,
  "distance_km": 50,
  "sites": ["linkedin", "indeed"],
  "linkedin_cookies": "optional cookie string"
}
"""
from __future__ import annotations

import json
import math
import sys

import jobspy


def clean(value):
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def sanitize(record: dict) -> dict:
    return {
        k: (v.isoformat() if hasattr(v, "isoformat") else clean(v))
        for k, v in record.items()
    }


def main() -> None:
    config = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}

    kwargs = {
        "site_name": config.get("sites", ["linkedin", "indeed"]),
        "search_term": " | ".join(config.get("queries", [])),
        "location": config.get("location", "Germany"),
        "results_wanted": config.get("results_per_query", 25),
        "hours_old": config.get("hours_old", 168),
        "country_indeed": "Germany",
        "distance": config.get("distance_km", 50),
        "is_remote": config.get("is_remote", False),
    }
    if config.get("linkedin_cookies"):
        kwargs["linkedin_str"] = config["linkedin_cookies"]

    jobs = jobspy.scrape_jobs(**kwargs)
    if hasattr(jobs, "to_dict"):
        jobs = jobs.to_dict("records")

    for job in jobs:
        print(json.dumps(sanitize(job), default=str))


if __name__ == "__main__":
    main()

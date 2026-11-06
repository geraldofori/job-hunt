"""Filter + score jobs in the DB. Sets status to 'shortlisted' or 'skipped'."""
from __future__ import annotations

import re

from common import db, get_logger, load_config

log = get_logger("match")

GERMAN_REQUIRED = re.compile(
    r"(fließend\w*\s+deutsch|fließend\w*\s+deutschkenntnisse|sehr gute\w*\s+deutschkenntnisse"
    r"|deutsch\s*(?:in\s+wort\s+und\s+schrift)?\s*(?:c1|c2|b2)|native\s+german|german\s+(?:c1|c2|b2))",
    re.I,
)
GERMAN_TEXT_HINTS = re.compile(r"\b(und|der|die|das|für|mit|wir|sie|ihre|unser|sind|bei|aus|auf)\b", re.I)


def detect_language(text: str) -> str:
    hits = len(GERMAN_TEXT_HINTS.findall(text[:2000]))
    return "de" if hits > 15 else "en"


def classify_work_model(title: str, desc: str, location: str, is_remote_flag) -> str:
    blob = f"{title} {desc[:3000]}".lower()
    if is_remote_flag or re.search(r"\b(100%\s*)?remote\b|homeoffice|home office", blob):
        if "hybrid" in blob:
            return "hybrid"
        return "remote"
    if "hybrid" in blob or "teilweise home" in blob:
        return "hybrid"
    return "onsite"


def job_passes_filters(job: dict, cfg: dict) -> tuple[bool, str]:
    f = cfg["filters"]
    title = job["title"].lower()
    blob = f"{job['title']}\n{job.get('description') or ''}".lower()

    for bad in f["exclude_title_terms"]:
        if bad in title:
            return False, f"excluded term: {bad}"
    if job["company"] and job["company"].lower() in [c.lower() for c in f["exclude_companies"]]:
        return False, "excluded company"

    if f["require_student_terms"] and not any(t in blob for t in f["student_terms"]):
        return False, "no student term"

    wm = job.get("work_model") or "unknown"
    loc = (job.get("location") or "").lower()
    if wm == "remote":
        return True, "remote"
    if any(c in loc for c in f["onsite_cities"]):
        return True, f"onsite city match"
    # location unknown / elsewhere in Germany and not remote -> reject
    return False, f"location not in scope: {job.get('location')}"


def score_job(job: dict, cfg: dict, profile: dict) -> float:
    s = cfg["scoring"]
    title = job["title"].lower()
    blob = f"{job['title']}\n{job.get('description') or ''}".lower()
    score = 0.0

    # Title-level signals are decisive when descriptions are short
    if re.search(r"werkstudent|working student|studentische|student\b", title):
        score += s.get("title_student_bonus", 2)
    tech_title = re.search(r"software|it\b|web|develop|engineer|programm|coding|frontend"
                 r"|backend|fullstack|embedded|informatik|digital|technolog|daten|cyber|system|"
                 r"anwendung|technik|elektron|automation|robot|ml\b|ki\b|ai\b|"
                 r"entwicklung|simulation|konstruktion|rechner|softwaretechnik", title)
    if tech_title:
        score += s.get("title_role_bonus", 2)
    else:
        score += s.get("off_role_title_penalty", -6)

    for kw in profile["skills"]["primary"]:
        if kw.lower() in blob:
            score += s["stack_primary_bonus"]
    for kw in profile["skills"]["secondary"]:
        if kw.lower() in blob:
            score += s["stack_secondary_bonus"]
    for kw in profile["skills"]["embedded"]:
        if kw.lower() in blob:
            score += s["embedded_bonus"]

    lang = job.get("language") or "en"
    if lang == "en":
        score += s["english_ok_bonus"]
    if GERMAN_REQUIRED.search(blob):
        score += s["german_required_penalty"]
    if job.get("easy_apply"):
        score += s["easy_apply_bonus"]

    # Geography: Saxony first, remote/home-office as the fallback tier.
    wm = (job.get("work_model") or "").lower()
    loc = (job.get("location") or "").lower()
    saxony = bool(re.search(r"chemnitz|leipzig|dresden|sachsen|saxony|"
                            r"zwickau|erfurt|görlitz|goerlitz|freiberg|meißen|meissen", loc))
    home_office = bool(re.search(r"home[ -]?office|remote möglich|ortsunabhängig|"
                                 r"remote work|work remotely|home[ -]?working", blob))
    if saxony and wm in ("onsite", "hybrid", "unknown", ""):
        score += s.get("saxony_onsite_bonus", 5)
    if wm == "remote" or (home_office and not saxony):
        score += s.get("remote_bonus", 2)
    if not saxony and wm == "onsite":
        score += s.get("elsewhere_onsite_penalty", -6)
    return score


def main() -> None:
    cfg = load_config("search.yaml")
    profile = load_config("profile.yaml")
    conn = db()
    rows = conn.execute("SELECT * FROM jobs WHERE status = 'new'").fetchall()
    short, skip = 0, 0
    for r in rows:
        job = dict(r)
        blob = f"{job['title']}\n{job.get('description') or ''}"
        job["language"] = detect_language(blob)
        job["work_model"] = classify_work_model(
            job["title"], job.get("description") or "", job.get("location") or "", None
        ) if job["work_model"] in (None, "unknown") else job["work_model"]

        ok, reason = job_passes_filters(job, cfg)
        if not ok:
            conn.execute(
                "UPDATE jobs SET status='skipped', notes=?, language=?, work_model=? WHERE id=?",
                (reason, job["language"], job["work_model"], job["id"]),
            )
            skip += 1
            continue
        score = score_job(job, cfg, profile)
        status = "shortlisted" if score >= cfg["scoring"]["min_score_to_apply"] else "skipped"
        conn.execute(
            "UPDATE jobs SET score=?, status=?, language=?, work_model=?, notes=? WHERE id=?",
            (score, status, job["language"], job["work_model"],
             None if status == "shortlisted" else f"score {score} below threshold", job["id"]),
        )
        short += status == "shortlisted"
        skip += status == "skipped"
    conn.commit()
    log.info("Matching complete: %d shortlisted, %d skipped", short, skip)
    print(f"SHORTLISTED={short} SKIPPED={skip}")


if __name__ == "__main__":
    main()

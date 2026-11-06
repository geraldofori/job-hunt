"""Shared helpers: paths, config loading, logging, SQLite job store."""
from __future__ import annotations

import json
import logging
import sqlite3
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
DATA = ROOT / "data"
DB = DATA / "jobs.db"
LOGS = ROOT / "logs"
COVER_LETTERS = ROOT / "cover_letters"
BROWSER_PROFILE = ROOT / "browser-profile"


def _applicant_name() -> tuple[str, str]:
    profile_path = CONFIG / "profile.yaml"
    if profile_path.exists():
        try:
            ident = load_config("profile.yaml")["identity"]
            return ident.get("first_name", "Applicant"), ident.get("last_name", "Applicant")
        except Exception:
            pass
    return "Applicant", "Applicant"


def cover_letter_name(company: str = "", role: str = "") -> str:
    """Short canonical basename: FirstName_LastName_Company (or _Role).

    Kept deliberately short — the job id lives in cover_letters/index.json
    instead of the filename, so these read well in a Downloads folder.
    """
    import re as _re

    first, last = _applicant_name()

    def _s(text: str, maxlen: int) -> str:
        text = _re.sub(r"[^0-9A-Za-zÀ-ɏ]+", "_", str(text)).strip("_")
        return text[:maxlen].strip("_") or "x"

    org = _s(company, 34) if company.strip() else _s(role, 40)
    return f"{_s(first, 20)}_{_s(last, 20)}_{org}"


def _letter_index() -> dict:
    idx = COVER_LETTERS / "index.json"
    if idx.exists():
        try:
            return json.loads(idx.read_text())
        except Exception:
            return {}
    return {}


def _letter_index_write(data: dict) -> None:
    COVER_LETTERS.mkdir(parents=True, exist_ok=True)
    (COVER_LETTERS / "index.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))


def cover_letter_paths(job_id: str, company: str = "", role: str = "") -> tuple[Path, Path]:
    """(markdown, pdf) paths for a job's cover letter under the canonical name."""
    idx = _letter_index()
    base = idx.get(job_id)
    if not base:
        base = cover_letter_name(company, role)
        idx[job_id] = base
        _letter_index_write(idx)
    return COVER_LETTERS / f"{base}.md", COVER_LETTERS / f"{base}.pdf"


def register_cover_letter(job_id: str, base: str) -> None:
    idx = _letter_index()
    idx[job_id] = base
    _letter_index_write(idx)


def find_cover_letter(job_id: str, company: str = "", role: str = "") -> tuple[Path | None, Path | None]:
    """Locate a job's cover letter, tolerating the older naming schemes."""
    md, pdf = cover_letter_paths(job_id, company, role)
    if pdf.exists():
        return (md if md.exists() else None), pdf
    for pattern in (f"*_{job_id}*.pdf", f"{job_id}.pdf", f"*{job_id}*.pdf"):
        hits = sorted(COVER_LETTERS.glob(pattern))
        if hits:
            found = hits[0]
            md_hit = found.with_suffix(".md")
            return (md_hit if md_hit.exists() else None), found
    return None, None


def load_config(name: str) -> dict:
    with open(CONFIG / name) as f:
        return yaml.safe_load(f)


def get_logger(name: str) -> logging.Logger:
    LOGS.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s")
        fh = logging.FileHandler(LOGS / "jobhunt.log")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


def db() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,          -- sha1 of (site + job_url)
            site TEXT,
            title TEXT,
            company TEXT,
            location TEXT,
            work_model TEXT,              -- remote / hybrid / onsite / unknown
            job_url TEXT,
            description TEXT,
            language TEXT,                -- en / de / unknown
            date_posted TEXT,
            easy_apply INTEGER DEFAULT 0,
            score REAL,
            status TEXT DEFAULT 'new',    -- new / shortlisted / skipped / applied / rejected_job
            first_seen TEXT DEFAULT (datetime('now')),
            applied_at TEXT,
            cover_letter_path TEXT,
            notes TEXT
        )
        """
    )
    conn.commit()
    return conn


def job_key(site: str, url: str) -> str:
    import hashlib

    return hashlib.sha1(f"{site}|{url}".encode()).hexdigest()[:16]

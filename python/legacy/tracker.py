"""Google Sheets tracker. One sheet 'Applications', one 'Dashboard'.

Auth: OAuth user token created by setup_google.py (token at config/google_token.json).
Spreadsheet id stored in config/gsheet.json.
"""
from __future__ import annotations

import json
from datetime import datetime

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from common import CONFIG, get_logger

log = get_logger("tracker")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.readonly",
]
TOKEN_PATH = CONFIG / "google_token.json"
GSHEET_META = CONFIG / "gsheet.json"

HEADERS = [
    "Date", "Company", "Role", "Platform", "Location", "Work Model",
    "URL", "Language", "Cover Letter", "Status", "Last Update", "Notes",
]
STATUSES = [
    "Applied", "Pending", "Reviewing", "Assessment",
    "Interview Scheduled", "Rejected", "Offer", "Withdrawn",
]


def get_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        raise SystemExit(
            "Google not authorized yet. Run: venv/bin/python scripts/setup_google.py"
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def get_sheet():
    creds = get_credentials()
    gc = gspread.authorize(creds)
    meta = json.loads(GSHEET_META.read_text())
    sh = gc.open_by_key(meta["spreadsheet_id"])
    try:
        ws = sh.worksheet("Applications")
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet("Applications", rows=2000, cols=len(HEADERS))
        ws.append_row(HEADERS)
        ws.freeze(rows=1)
    return ws


def add_application(job: dict, cover_letter: str = "", status: str = "Applied") -> None:
    ws = get_sheet()
    today = datetime.now().strftime("%Y-%m-%d")
    ws.append_row(
        [
            today,
            job.get("company", ""),
            job.get("title", ""),
            job.get("site", ""),
            job.get("location", ""),
            job.get("work_model", ""),
            job.get("job_url", ""),
            job.get("language", ""),
            cover_letter,
            status,
            today,
            job.get("notes", ""),
        ],
        value_input_option="USER_ENTERED",
    )
    log.info("Tracked: %s @ %s", job.get("title"), job.get("company"))


def _find_row(ws, company: str, role: str) -> int | None:
    rows = ws.get_all_values()
    for i, row in enumerate(rows[1:], start=2):
        if len(row) >= 3 and row[1].lower() == company.lower() and row[2].lower() == role.lower():
            return i
    return None


def update_status(company: str, role: str, status: str, notes: str = "") -> bool:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    ws = get_sheet()
    row = _find_row(ws, company, role)
    if not row:
        log.warning("No row found for %s / %s", company, role)
        return False
    ws.update_cell(row, 10, status)
    ws.update_cell(row, 11, datetime.now().strftime("%Y-%m-%d %H:%M"))
    if notes:
        ws.update_cell(row, 12, notes)
    log.info("Status -> %s: %s @ %s", status, role, company)
    return True


def list_open_applications() -> list[dict]:
    """Rows whose status is still active (used by gmail_monitor)."""
    ws = get_sheet()
    rows = ws.get_all_records()
    return [
        r for r in rows
        if r.get("Status") in ("Applied", "Pending", "Reviewing", "Assessment")
    ]


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 4 and sys.argv[1] == "update":
        update_status(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else "Pending")
    else:
        print("tracker OK — sheet rows:", len(get_sheet().get_all_values()))

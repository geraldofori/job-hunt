"""Scan Gmail for replies related to tracked applications and update the sheet.

Classification heuristics (EN+DE). Interview/assessment hits trigger a macOS
notification. Everything is also written to logs/gmail_report.txt for review.
"""
from __future__ import annotations

import base64
import json
import re
import subprocess
from datetime import datetime

from googleapiclient.discovery import build

from common import LOGS, get_logger
from tracker import get_credentials, list_open_applications, update_status

log = get_logger("gmail")

# (status, pattern) — checked in order, first match wins
RULES = [
    ("Interview Scheduled", re.compile(
        "interview|vorstellungsgespraech|einladung|schedule a call|"
        "kennenlern|termin (vorschlagen|vereinbaren)|invitation to", re.I)),
    ("Assessment", re.compile(
        "assessment|coding (challenge|task|test)|take-home|hackerrank|codility|"
        "online test|arbeitsprobe", re.I)),
    ("Rejected", re.compile(
        "unfortunately|leider (nicht|kein)|absage|not moving forward|"
        "other candidates|nicht beruecksichtigt|position (has )?(been )?filled|"
        "regret to inform", re.I)),
    ("Reviewing", re.compile(
        "received (your )?application|bewerbung (erhalten|eingegangen)|"
        "eingangsbestaetigung|under review|wi?rd geprueft|thank you for (your )?(application|interest)",
        re.I)),
]


def normalize_de(text: str) -> str:
    """Fold umlauts so patterns above match both written variants."""
    return (text.replace("ä", "ae").replace("ö", "oe").replace("ue", "ue")
                .replace("ü", "ue").replace("ß", "ss"))


def classify(text: str) -> str | None:
    t = normalize_de(text)
    for status, pat in RULES:
        if pat.search(t):
            return status
    return None


def notify(title: str, msg: str) -> None:
    script = "display notification {0} with title {1}".format(
        json.dumps(msg), json.dumps(title))
    subprocess.run(["osascript", "-e", script], check=False)


def decode_payload(msg_data: dict) -> tuple[str, str, dict]:
    headers = {h["name"].lower(): h["value"] for h in msg_data.get("headers", [])}
    body = ""
    parts = [msg_data.get("payload", {})]
    while parts:
        p = parts.pop(0)
        data = p.get("body", {}).get("data")
        if data:
            try:
                body += base64.urlsafe_b64decode(data + "==").decode(errors="ignore")
            except Exception:
                pass
        parts.extend(p.get("parts", []))
    body = re.sub("<[^>]+>", " ", body)[:4000]
    return headers.get("from", ""), headers.get("subject", ""), body


def search(service, query: str, max_results: int = 8) -> list[dict]:
    resp = service.users().messages().list(
        userId="me", q=query, maxResults=max_results).execute()
    out = []
    for m in resp.get("messages", []):
        d = service.users().messages().get(
            userId="me", id=m["id"],
            format="full").execute()
        out.append(d)
    return out


def main() -> None:
    creds = get_credentials()
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    open_apps = list_open_applications()
    if not open_apps:
        log.info("No open applications to monitor.")
        return

    report_lines = [f"Gmail scan {datetime.now():%Y-%m-%d %H:%M} "
                    f"- {len(open_apps)} open applications"]
    for app in open_apps:
        company = str(app.get("Company") or "").strip()
        role = str(app.get("Role") or "").strip()
        current = str(app.get("Status") or "")
        if not company:
            continue
        q = (f'"{company}" (application OR interview OR bewerbung OR status) '
             "newer_than:60d")
        try:
            msgs = search(service, q)
        except Exception as e:
            log.warning("Gmail search failed for %s: %s", company, e)
            continue
        best_status, best_subject = None, ""
        for d in msgs:
            sender, subject, body = decode_payload(d)
            if "noreply" in sender and current != "Applied":
                pass  # automated acks still count for Reviewing
            s = classify(subject + "\n" + body)
            if s and best_status is None:
                best_status, best_subject = s, subject
            if s == "Interview Scheduled":
                break
        if best_status and best_status != current:
            update_status(company, role, best_status,
                          notes=f"auto-classified from email: {best_subject[:120]}")
            report_lines.append(f"{company}: {current} -> {best_status}")
            if best_status in ("Interview Scheduled", "Assessment", "Offer"):
                notify("Job hunt update", f"{company}: {best_status}")
        elif not best_status:
            report_lines.append(f"{company}: no reply detected")

    report = "\n".join(report_lines)
    (LOGS / "gmail_report.txt").write_text(report)
    log.info("Gmail monitor done.")
    print(report)


if __name__ == "__main__":
    main()

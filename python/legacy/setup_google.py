"""One-time Google setup: OAuth consent (browser opens), token saved,
tracking spreadsheet created.

Prereq: config/google_client_secret.json — a Desktop-app OAuth client from
console.cloud.google.com with Sheets API + Gmail API enabled.
(The script explains exactly how if the file is missing.)
"""
from __future__ import annotations

import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from common import CONFIG

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/gmail.readonly",
]
CLIENT_SECRET = CONFIG / "google_client_secret.json"
TOKEN_PATH = CONFIG / "google_token.json"
GSHEET_META = CONFIG / "gsheet.json"

INSTRUCTIONS = """
Missing config/google_client_secret.json

Create it (5 min, one time):
1. Go to https://console.cloud.google.com/  (log in with oforige@gmail.com)
2. Create a project (e.g. 'job-hunt')
3. APIs & Services -> Library -> enable 'Google Sheets API' and 'Gmail API'
4. APIs & Services -> OAuth consent screen -> External -> fill app name,
   add your email as test user (IMPORTANT: add oforige@gmail.com under
   'Test users' or the token will be rejected)
5. APIs & Services -> Credentials -> Create Credentials -> OAuth client ID
   -> Application type: Desktop app -> Download JSON
6. Save the downloaded file as:
   /Users/geraldofori/job-hunt/config/google_client_secret.json
Then re-run this script.
"""


def main() -> None:
    if not CLIENT_SECRET.exists():
        print(INSTRUCTIONS)
        sys.exit(1)

    creds = None
    if TOKEN_PATH.exists():
        from google.oauth2.credentials import Credentials
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            creds = None
    if not creds or not (creds.valid or creds.refresh_token):
        flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
        creds = flow.run_local_server(port=8090, prompt="consent")
        TOKEN_PATH.write_text(creds.to_json())
    print("Token saved.")

    import gspread
    from googleapiclient.discovery import build

    sheets = build("sheets", "v4", credentials=creds, cache_discovery=False)
    # Create via Sheets API (avoids needing the Drive API enabled in GCP)
    created = sheets.spreadsheets().create(body={
        "properties": {"title": "Job Applications — Gerald Ofori"}}).execute()
    sheet_id = created["spreadsheetId"]
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(sheet_id)
    ws = sh.sheet1
    ws.update_title("Applications")
    headers = [
        "Date", "Company", "Role", "Platform", "Location", "Work Model",
        "URL", "Language", "Cover Letter", "Status", "Last Update", "Notes",
    ]
    ws.append_row(headers)
    ws.freeze(rows=1)
    ws.format(f"A1:L1", {"textFormat": {"bold": True}})

    dash = sh.add_worksheet("Dashboard", rows=20, cols=4)
    dash.append_row(["Metric", "Value"])
    dash.append_row(["Total applications", '=COUNTA(Applications!B2:B)'])
    dash.append_row(["Responses", '=COUNTIF(Applications!J:J,"Reviewing")+COUNTIF(Applications!J:J,"Assessment")+COUNTIF(Applications!J:J,"Interview Scheduled")+COUNTIF(Applications!J:J,"Rejected")+COUNTIF(Applications!J:J,"Offer")'])
    dash.append_row(["Interviews", '=COUNTIF(Applications!J:J,"Interview Scheduled")'])
    dash.append_row(["Offers", '=COUNTIF(Applications!J:J,"Offer")'])
    dash.append_row(["Rejections", '=COUNTIF(Applications!J:J,"Rejected")'])

    GSHEET_META.write_text(json.dumps({"spreadsheet_id": sh.id, "url": sh.url}, indent=2))
    print(f"Spreadsheet created: {sh.url}")


if __name__ == "__main__":
    main()

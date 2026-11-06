# Job Hunt — automated Werkstudent applications

Daily system: discovers Werkstudent roles (frontend + embedded) for Chemnitz/Leipzig/Dresden + remote Germany, scores them against Gerald's CV, auto-submits LinkedIn Easy Apply, queues company portals for approval, tracks everything in Google Sheets, and monitors Gmail for responses.

## Daily operation
- **10:00 launchd run** (`com.gerald.jobhunt.daily`): discovery → matching → LinkedIn Easy Apply auto-submit → Gmail response scan → daily brief + macOS notification.
- Results: `data/runs/YYYY-MM-DD_brief.md`, queue in `data/approval_queue.md`, tracker sheet in Google Sheets.

## One-time setup checklist
1. **Google credentials** (Sheets + Gmail):
   - Follow the instructions printed by `venv/bin/python scripts/setup_google.py`
   - Save OAuth client JSON as `config/google_client_secret.json`, run the script once.
2. **Logins** (once, sessions persist in `browser-profile/`):
   ```
   venv/bin/python scripts/login_session.py https://www.linkedin.com  # log in fully
   venv/bin/python scripts/login_session.py https://de.indeed.com
   venv/bin/python scripts/login_session.py https://myaccount.google.com
   ```
3. **install launchd job**:
   ```
   cp scripts/com.gerald.jobhunt.daily.plist ~/Library/LaunchAgents/
   launchctl load ~/Library/LaunchAgents/com.gerald.jobhunt.daily.plist
   ```

## Manual commands
```
./venv/bin/python scripts/daily.py --no-apply    # discovery + matching only
./venv/bin/python scripts/daily.py               # full run
./venv/bin/python scripts/apply_queue.py         # process portal queue (headful, you approve submits)
./venv/bin/python scripts/gmail_monitor.py       # response scan only
sqlite3 data/jobs.db "SELECT score,title,company,location,status FROM jobs ORDER BY score DESC LIMIT 20;"
```

## Cover letters
Written by the agent with the `gerald-voice` skill, saved to
`cover_letters/<jobid>.pdf`; the queue runner uploads them when present.
Ask: *"Write cover letters for the approval queue"* in an opencode session.

## Safety notes
- LinkedIn automation violates ToS in principle; keep volume low (≤8/day),
  human pacing, real browser profile. The system is built for that.
- The engine **never** submits an external portal without the human pressing
  Enter; LinkedIn Easy Apply auto-submits only when the form was fully
  answerable — unknown required questions abort that application cleanly.

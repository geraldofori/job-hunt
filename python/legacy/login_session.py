"""Open the persistent browser profile for manual logins.

Usage: venv/bin/python scripts/login_session.py [url]

Log into each site once; sessions persist in browser-profile/.
Recommended order: gmail.com (Google) -> linkedin.com -> indeed.de -> stepstone.de
Press Ctrl+C here when done; the browser closes and sessions are saved.
"""
from __future__ import annotations

import sys

from apply_engine import open_browser

url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com"

pw, ctx = open_browser(headless=False)
page = ctx.pages[0] if ctx.pages else ctx.new_page()
page.goto(url)
print(f"Browser open at {url}. Log in, then press Ctrl+C in this terminal to finish.")
try:
    while True:
        page.wait_for_timeout(1000)
except KeyboardInterrupt:
    pass
finally:
    ctx.close()
    pw.stop()
    print("Sessions saved to browser-profile/")

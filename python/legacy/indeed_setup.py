"""Indeed onboarding: user logs in once, then we upload the latest CV.

1. Opens the login page in the persistent browser profile.
2. Waits (up to 15 min) for the user to sign in — polls for the signed-in home.
3. Opens the resume manager and uploads resume/Gerald_Ofori_Lebenslauf.pdf.
4. Verifies the upload by re-reading the resume list.

Usage: venv/bin/python scripts/indeed_setup.py
"""
from __future__ import annotations

import sys
import time

from playwright.sync_api import sync_playwright

from common import ROOT, load_config

CV = ROOT / load_config("profile.yaml")["documents"]["cv_pdf"]
HOME = "https://de.indeed.com/"
SIGNED_IN_MARKERS = ("Mein Konto", "My Account", "Meine Jobs", "Meine Gesuche",
                     "job searches", "my jobs")


def signed_in(pg) -> bool:
    try:
        body = pg.inner_text("body", timeout=5000)
    except Exception:
        return False
    return any(m.lower() in body.lower() for m in SIGNED_IN_MARKERS)


def main() -> int:
    if not CV.exists():
        print(f"CV missing: {CV}"); return 1
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()

        print("[1] checking existing session...")
        pg.goto(HOME, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(4000)
        if not signed_in(pg):
            print("[2] not signed in -> opening login")
            pg.goto("https://account.indeed.com/auth?rd=https%3A%2F%2Fde.indeed.com%2F",
                    wait_until="domcontentloaded", timeout=60000)
            print("    >>> Gerald: sign in in this window now (email+password). <<<")
            deadline = time.time() + 900
            while time.time() < deadline:
                pg.wait_for_timeout(5000)
                try:
                    if "account.indeed.com" not in pg.url and "auth" not in pg.url:
                        pg.goto(HOME, wait_until="domcontentloaded", timeout=30000)
                        pg.wait_for_timeout(3000)
                        if signed_in(pg):
                            break
                except Exception:
                    pass
            else:
                print("    timed out waiting for login")
                ctx.close(); return 2
        print(f"    signed in. url: {pg.url}")

        print("[3] open resume manager")
        uploaded = False
        for url in ("https://de.indeed.com/mycv", "https://my.indeed.com/cv",
                    "https://de.indeed.com/settings/resumes"):
            try:
                pg.goto(url, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(3500)
            except Exception as e:
                print(f"  {url} failed: {str(e)[:50]}"); continue
            fi = pg.locator("input[type='file']")
            if fi.count():
                try:
                    fi.first.set_input_files(str(CV))
                    uploaded = True
                    print(f"  uploaded via hidden input on {url}")
                    break
                except Exception as e:
                    print(f"  set_input_files failed: {str(e)[:60]}")
            # look for an explicit upload control
            btn = pg.locator("text=/upload a resume|lebenslauf hochladen|add resume|"
                             "resume hochladen/i").first
            if btn.count():
                try:
                    with pg.expect_file_chooser(timeout=5000) as info:
                        btn.click()
                    info.value.set_files(str(CV))
                    uploaded = True
                    print(f"  uploaded via chooser on {url}")
                    break
                except Exception as e:
                    print(f"  chooser failed: {str(e)[:60]}")
        if not uploaded:
            print("  could not find the upload control")
            pg.screenshot(path=str(ROOT / "logs/setup/indeed_cv_nocontrol.png"))
            print("  page text:", pg.inner_text("body")[:400].replace("\n", " "))
            ctx.close(); return 3

        print("[4] confirm")
        pg.wait_for_timeout(6000)
        pg.screenshot(path=str(ROOT / "logs/setup/indeed_cv_done.png"))
        body = pg.inner_text("body")
        print("  CV filename visible:", CV.name.split(".")[0].lower() in body.lower()
              or "lebenslauf" in body.lower())
        print("  saved/added hint:", any(k in body.lower() for k in
              ("saved", "gespeichert", "added", "hinzugefügt", "uploaded", "hochgeladen")))
        ctx.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())

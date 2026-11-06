"""Fix the draft's phone via real keystrokes in the contact-info module.

Learned: raw value-injection is reverted on save. So: Review -> Bearbeiten
(contact) -> focus phone input -> select-all + type -> any country selector
through its dropdown -> Weiter -> confirm +49 on review -> submit.

Usage: venv/bin/python scripts/indeed_fix_contact2.py [jk] [--submit]
"""
from __future__ import annotations

import re
import sys

from playwright.sync_api import sync_playwright

from common import ROOT, get_logger, load_config

log = get_logger("indeed-fix")
JK = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "b804c4497a600281"
DO_SUBMIT = "--submit" in sys.argv
PHONE = "".join(c for c in load_config("profile.yaml")["identity"]["phone"] if c.isdigit())
LOCAL = PHONE[2:] if PHONE.startswith("49") else PHONE
SHOTS = ROOT / "logs"


def smart(pg):
    return next((f for f in pg.frames if "smartapply" in (f.url or "")), None)


def weiter(fr):
    fr.evaluate("""() => { const els=[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&
        /^(weiter|continue|next)$/i.test((e.textContent||'').trim())&&!/übersicht/i.test(e.textContent||''));
        els.length && els[els.length-1].click(); }""")


def to_review(pg, rounds=8):
    for _ in range(rounds):
        pg.wait_for_timeout(3000)
        fr = smart(pg)
        if not fr:
            continue
        try:
            t = fr.evaluate("() => document.body.innerText")
        except Exception:
            continue
        if re.search(r"Review your application", t):
            return fr
        weiter(fr)
    return None


def edit_phone_in_contact(fr) -> None:
    """Human-style rewrite of the phone field."""
    tel = fr.locator("input[type='tel'], input[aria-label*='hone' i], input[aria-label*='elefon' i]").first
    tel.wait_for(state="visible", timeout=15000)
    # country first if a selector exists
    cc = fr.locator("button[aria-label*='Country code']")
    if cc.count():
        cc.first.click()
        fr.wait_for_timeout(2000)
        opt = fr.locator("[role='option'], li, [role='menuitem']", has_text=re.compile("germany|deutschland", re.I))
        if opt.count():
            opt.last.click()
            log.info("country -> Germany")
            fr.wait_for_timeout(1500)
    tel.click(click_count=3)
    tel.press("Control+A")
    tel.press("Delete")
    tel.type(LOCAL, delay=70)
    tel.press("Tab")
    fr.wait_for_timeout(1500)
    now = tel.input_value()
    log.info("contact phone field now: %r", now)


def main() -> int:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 1600})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(f"https://de.indeed.com/viewjob?jk={JK}", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(8000)
        pg.evaluate("""() => [...document.querySelectorAll('a,button')].find(x=>x.offsetParent&&
            /schnellbewerbung|quick apply/i.test((x.textContent||'').trim()))?.click()""")
        pg.wait_for_timeout(12000)

        # If the wizard reopened on contact-info directly, fix it there.
        fr = smart(pg)
        url = (fr.url if fr else pg.url) or ""
        if "contact-info" in url:
            edit_phone_in_contact(fr)
            weiter(fr)
        rev = to_review(pg)
        if not rev:
            print("no review reached")
            pg.screenshot(path=str(SHOTS / "fix2_norev.png"))
            ctx.close(); return 2

        # click the Kontaktdaten 'Bearbeiten' (first occurrence), then fix phone
        rev.locator("text=Bearbeiten").first.click(timeout=15000)
        pg.wait_for_timeout(12000)
        fr = smart(pg)
        if fr and "contact-info" in (fr.url or ""):
            edit_phone_in_contact(fr)
            weiter(fr)
            rev = to_review(pg)
        else:
            print("Bearbeiten did not lead to contact module:", (fr.url if fr else "")[:70])

        if rev:
            t = rev.evaluate("() => document.body.innerText")
            m = re.search(r"Telefonnummer\s*\n\s*([^\n]+)", t)
            phone_line = m.group(1).strip() if m else "n/a"
            print("review phone:", phone_line)
            pg.screenshot(path=str(SHOTS / "fix2_review.png"), full_page=True)
            if "+233" in phone_line or not DO_SUBMIT:
                print("not submitting" if "+233" in phone_line else "dry stop")
                ctx.close(); return 3
            btn = rev.locator("button", has_text=re.compile("bewerbung absenden|send application", re.I)).first
            btn.click(timeout=8000)
            pg.wait_for_timeout(9000)
            t2 = rev.evaluate("() => document.body.innerText")
            ok = bool(re.search(r"gesendet|submitted|vielen dank|danke", t2, re.I))
            print("SUBMITTED" if ok else "unclear result after click")
            pg.screenshot(path=str(SHOTS / "fix2_done.png"), full_page=True)
        ctx.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())

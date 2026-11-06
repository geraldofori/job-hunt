"""Single polite pass: walk the 1KOMMA5 wizard end-to-end and submit.

Combines the pieces proven during exploration:
  * engine answers the contact/questions steps (real fills, not blind Weiter)
  * phone rewritten with keystrokes; review re-checked for stale +233
  * submits only when the review shows +49

Exits NEED_WALL if Cloudflare reappears (cooldown too short).

Usage: venv/bin/python scripts/indeed_finish.py [jk] [--submit]
"""
from __future__ import annotations

import re
import sys
import time

from playwright.sync_api import sync_playwright

from common import ROOT, get_logger, load_config
from indeed_apply import IndeedApply
from indeed_fix_contact2 import edit_phone_in_contact

log = get_logger("finish")
JK = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "b804c4497a600281"
DO_SUBMIT = "--submit" in sys.argv


def wall(pg) -> bool:
    try:
        return "Verification" in pg.inner_text("body", timeout=4000)
    except Exception:
        return False


def main() -> int:
    profile = load_config("profile.yaml")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 1400})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        eng = IndeedApply(pg, profile)
        pg.goto(f"https://de.indeed.com/viewjob?jk={JK}", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(10000)
        if wall(pg):
            print("NEED_WALL at entry"); ctx.close(); return 7
        btn = pg.locator("text=Schnellbewerbung")
        if not btn.count():
            print("no apply button"); ctx.close(); return 2
        btn.first.click()
        pg.wait_for_timeout(12000)

        for step in range(16):
            if wall(pg):
                print("NEED_WALL mid-flow"); ctx.close(); return 7
            fr = eng.form_frame()
            if fr is None:
                pg.wait_for_timeout(6000)
                continue
            try:
                url = fr.url or ""
                t = fr.evaluate("() => document.body.innerText")
            except Exception:
                pg.wait_for_timeout(6000); continue

            if re.search(r"Review your application", t):
                m = re.search(r"Telefonnummer\s*\n\s*([^\n]+)", t)
                phone = (m.group(1).strip() if m else "n/a")
                print("review phone:", phone)
                if "+233" in phone:
                    print("stale phone on review -> editing contact")
                    pg.locator("iframe").first.content_frame()  # touch
                    ok = fr.evaluate("""() => { const a=[...document.querySelectorAll('a,button,[role=button]')]
                        .find(e=>e.offsetParent&&/^(bearbeiten|edit)$/i.test((e.textContent||'').trim()));
                        if(a){a.click();return true} return false; }""")
                    pg.wait_for_timeout(12000)
                    fr = eng.form_frame()
                    if fr and ok:
                        edit_phone_in_contact(fr)
                        fr.evaluate("""() => { const els=[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&
                            /^(weiter|continue|next)$/i.test((e.textContent||'').trim())&&!/übersicht/i.test(e.textContent||''));
                            els.length && els[els.length-1].click(); }""")
                        pg.wait_for_timeout(12000)
                        continue
                    print("could not reopen contact editor"); ctx.close(); return 4
                if not DO_SUBMIT:
                    print("dry-run stop at review"); ctx.close(); return 0
                clicked = fr.evaluate("""() => { const b=[...document.querySelectorAll('button')].find(e=>e.offsetParent&&
                    /bewerbung absenden|send application/i.test((e.textContent||'').trim()));
                    if(!b) return false; b.click(); return true; }""")
                print("submit clicked:", clicked)
                pg.wait_for_timeout(12000)
                t2 = fr.evaluate("() => document.body.innerText")
                ok = bool(re.search(r"gesendet|submitted|vielen dank|danke|thank you", t2, re.I))
                pg.screenshot(path=str(ROOT / "logs" / "finish_result.png"), full_page=True)
                print("SUBMITTED" if ok else "SUBMIT_UNCONFIRMED")
                ctx.close()
                return 0 if ok else 5

            if "contact-info" in url:
                try:
                    edit_phone_in_contact(fr)
                except Exception as e:
                    print("contact edit failed:", str(e)[:70])
            elif "resume-selection" in url:
                eng.resume_step(fr)
            elif "questions" in url:
                eng.answer_step(fr)
                if eng.unknown:
                    print("unknown required questions:", eng.unknown)
                    pg.screenshot(path=str(ROOT / "logs" / "finish_unknown.png"))
                    ctx.close(); return 3

            fr.evaluate("""() => { const els=[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&
                /^(weiter|continue|next)$/i.test((e.textContent||'').trim())&&!/übersicht/i.test(e.textContent||''));
                els.length && els[els.length-1].click(); }""")
            time.sleep(14)  # human-ish pacing between steps
        print("finished loop without review")
        ctx.close()
        return 6


if __name__ == "__main__":
    sys.exit(main())

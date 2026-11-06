"""One-off: replace the stale +233 phone in the open 1KOMMA5 draft.

Flow learned from exploration: Review -> click 'Bearbeiten' (React div, not a
button) -> navigates to contact-info module -> rewrite phone -> Weiter back
through the wizard -> verify on review.

Usage: venv/bin/python scripts/indeed_fix_contact.py [jk]
"""
from __future__ import annotations

import json
import re
import sys

from playwright.sync_api import sync_playwright

from common import ROOT, load_config

JK = sys.argv[1] if len(sys.argv) > 1 else "b804c4497a600281"
PROFILE = load_config("profile.yaml")
PHONE = "".join(c for c in PROFILE["identity"]["phone"] if c.isdigit())
LOCAL = PHONE[2:] if PHONE.startswith("49") else PHONE   # 15907981322
SHOTS = ROOT / "logs"


def smartapply(pg):
    return next((f for f in pg.frames if "smartapply" in (f.url or "")), None)


def click_weiter(fr) -> None:
    fr.evaluate("""() => { const els=[...document.querySelectorAll('button')].filter(e=>e.offsetParent&&
        /^(weiter|continue|next)$/i.test((e.textContent||'').trim())&&!/übersicht/i.test(e.textContent||''));
        els.length && els[els.length-1].click(); }""")


def click_edit_on_review(fr) -> None:
    fr.evaluate("""() => { const all=[...document.querySelectorAll('*')].filter(e=>e.offsetParent&&
        /^(bearbeiten|edit)$/i.test((e.textContent||'').trim()));
        all.sort((a,b)=>b.outerHTML.length-a.outerHTML.length);
        const el=all[0]; ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t=>
            el.dispatchEvent(new MouseEvent(t,{bubbles:true,cancelable:true,view:window}))); }""")


def rewrite_phone(fr) -> None:
    fr.evaluate("""(phone) => {
        const tel = document.querySelector("input[type='tel']");
        if (!tel) return false;
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
        tel.focus();
        setter.set.call(tel, phone);
        ['input','change','blur'].forEach(t => tel.dispatchEvent(new Event(t, {bubbles:true})));
        return true;
    }""", LOCAL)
    # country code selector on the contact card, if shown
    cc = fr.locator("button[aria-label*='Country code']")
    if cc.count():
        cc.first.click()
        fr.wait_for_timeout(1800)
        got = fr.evaluate("""() => { const items=[...document.querySelectorAll('[role=option],li,[role=menuitem],div,button')]
            .filter(e=>e.offsetParent&&/germany|deutschland/i.test(e.textContent||'')&&e.textContent.trim().length<40);
            if(!items.length) return null; items[items.length-1].click();
            return items[items.length-1].textContent.trim().slice(0,26); }""")
        print("country picked:", got)
        fr.wait_for_timeout(1200)
    print("phone rewritten to", LOCAL)


def main() -> int:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 1200})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(f"https://de.indeed.com/viewjob?jk={JK}", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        pg.evaluate("""() => [...document.querySelectorAll('a,button')].find(x=>x.offsetParent&&
            /schnellbewerbung|quick apply/i.test((x.textContent||'').trim()))?.click()""")

        # 1) walk to review
        rev = None
        for _ in range(12):
            pg.wait_for_timeout(3500)
            fr = smartapply(pg)
            if not fr:
                continue
            try:
                t = fr.evaluate("() => document.body.innerText")
            except Exception:
                continue
            if re.search(r"Review your application|Überprüfen", t):
                rev = fr
                break
            if re.search(r"Kontaktdaten hinzufügen|contact-info", (fr.url or "") + t):
                rewrite_phone(fr)
                click_weiter(fr)
                continue
            click_weiter(fr)
        if not rev:
            print("never reached review"); pg.screenshot(path=str(SHOTS / "fix_noreview.png"))
            ctx.close(); return 2

        # 2) edit contact from review
        try:
            click_edit_on_review(rev)
        except Exception as e:
            print("edit click failed:", str(e)[:60])
        pg.wait_for_timeout(12000)
        fr = smartapply(pg)
        if fr and "contact" not in (fr.url or ""):
            # try again: deepest element with 'Bearbeiten'
            try:
                click_edit_on_review(fr)
                pg.wait_for_timeout(12000)
                fr = smartapply(pg)
            except Exception:
                pass
        print("now at:", (fr.url if fr else pg.url)[:80])
        rewrite_phone(fr)
        click_weiter(fr)

        # 3) forward to review, verify phone card
        final = ""
        for _ in range(10):
            pg.wait_for_timeout(3500)
            fr = smartapply(pg)
            if not fr:
                continue
            try:
                final = fr.evaluate("() => document.body.innerText")
            except Exception:
                continue
            if re.search(r"Review your application", final):
                break
            click_weiter(fr)
        m = re.search(r"(\+\d{2,3}[\s\d]{6,14})", final or "")
        print("review phone snippet:", repr(m.group(1)) if m else "n/a")
        print("contains +49:", "+49" in final, "| contains +233:", "+233" in final)
        pg.screenshot(path=str(SHOTS / "fix_review_after.png"), full_page=True)
        ctx.close()
        return 0 if "+233" not in final else 3


if __name__ == "__main__":
    sys.exit(main())

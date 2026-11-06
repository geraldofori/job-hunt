"""Update the phone number stored in the Indeed profile (country code + number).

Indeed formats German mobiles as +49 followed by the number WITHOUT the
leading 0: +49 1590 7981322 -> local '15907981322'.

Usage: venv/bin/python scripts/indeed_phone.py
"""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

from common import ROOT, load_config

PHONE = load_config("profile.yaml")["identity"]["phone"]
SHOTS = ROOT / "logs" / "setup"


def main() -> int:
    digits = "".join(c for c in PHONE if c.isdigit())
    if digits.startswith("49"):
        local = digits[2:]          # 49 1590... -> 1590...
    else:
        local = digits
    print(f"profile phone {PHONE!r} -> country +49, local {local!r}")

    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto("https://profile.indeed.com/", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(9000)

        # The header renders the stored phone as a button ('+233 50 …' etc.)
        btn = pg.locator("button", has_text="+")
        if not btn.count():
            print("no phone button found")
            print(json.dumps(pg.eval_on_selector_all(
                "button", "els=>els.filter(e=>e.offsetParent).map(e=>e.textContent.trim().slice(0,34))")[:14]))
            ctx.close(); return 1
        btn.first.click()
        pg.wait_for_timeout(3500)
        if "about" not in pg.url.lower() and "profile" not in pg.url.lower():
            print("unexpected url:", pg.url)

        # country code widget: <button aria-label="Country code, 🇬🇭 +233">
        trig = pg.locator("button[aria-label*='Country code']").first
        if not trig.count():
            print("no country-code button")
        else:
            trig.click()
            pg.wait_for_timeout(2000)
            got = pg.evaluate("""() => {
                const items = [...document.querySelectorAll('[role=option], li, [role=menuitem], button, div')]
                    .filter(e => e.offsetParent && /germany|deutschland/i.test(e.textContent || '')
                        && e.textContent.trim().length < 40);
                if (!items.length) return null;
                items[items.length - 1].click();
                return items[items.length - 1].textContent.trim().slice(0, 40);
            }""")
            print("country picked:", got)
            pg.wait_for_timeout(1500)

        tel = pg.locator("input[type='tel']").first
        if tel.count():
            tel.click(); tel.fill("")
            tel.type(local, delay=50)
            print(f"phone -> {local}")
        else:
            print("no tel input")
        pg.wait_for_timeout(800)
        err = pg.evaluate("() => /valid phone|ungültig|invalid/i.test(document.body.innerText)")
        print("validation error present:", err)
        pg.screenshot(path=str(SHOTS / "phone_fixed_form.png"))
        if err:
            ctx.close(); return 2

        for sel in ("button:has-text('Save')", "button:has-text('Speichern')"):
            b = pg.locator(sel)
            if b.count() and b.first.is_visible():
                b.first.click()
                print("saved via", sel)
                break
        pg.wait_for_timeout(4500)
        pg.screenshot(path=str(SHOTS / "phone_fixed_after.png"))
        body = pg.inner_text("body")
        print("header shows +49:", "+49" in body)
        ctx.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())

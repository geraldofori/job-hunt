"""Fix 'Open to Work' locations: drop Ghana, add Chemnitz.

Path: profile -> Open-to-work card -> Show details -> 'Edit job preferences'
anchor -> dialog with chip buttons. Verified against the live DOM: the Ghana
chip is a <button> whose text is 'Ghana'; adding uses the 'Add location'
button + typeahead. Saves with 'Save'.

Usage:
  venv/bin/python scripts/open_to_work_locations.py --dry-run   # inspect only
  venv/bin/python scripts/open_to_work_locations.py             # edit + save
"""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

from common import ROOT, load_config

DROP, ADD = "Ghana", "Chemnitz"
DRY = "--dry-run" in sys.argv
SHOTS = ROOT / "logs" / "setup"

HUB_TEXT = """() => [...document.querySelectorAll('*')].some(e =>
        e.offsetParent && /^edit job preferences/i.test((e.textContent||'').trim()) &&
        (e.textContent||'').trim().length < 40)"""

FORM_DLG = """() => {
    const title = [...document.querySelectorAll('*')].find(e => !e.children.length && e.offsetParent &&
        /^edit job preferences$/i.test((e.textContent||'').trim()));
    let dlg = title;
    while (dlg && dlg.tagName !== 'DIALOG') dlg = dlg.parentElement;
    window.__otwDialog = dlg;
    return !!dlg;
}"""


def pick_option(pg, expect: str):
    return pg.evaluate("""(exp) => {
        const root = window.__otwDialog || document;
        const opts = [...root.querySelectorAll("[role='option'], li[role='option'], .artdeco-typeahead__result")];
        const hit = opts.find(o => ((o.textContent||'').toLowerCase().includes(exp)) && o.offsetWidth > 0);
        if (!hit) return null;
        hit.click();
        return (hit.textContent||'').trim().slice(0,48);
    }""", expect.lower())


def open_hub(pg) -> bool:
    """Show details -> hub. LinkedIn sometimes swallows the click behind a
    promo backdrop, so retry from scratch."""
    for attempt in range(3):
        if attempt:
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(1200)
        sd = pg.locator("text=/Show details|Details anzeigen/i")
        if not sd.count():
            pg.reload(wait_until="domcontentloaded"); pg.wait_for_timeout(6000)
            continue
        sd.first.click()
        btn = pg.locator("button[aria-label*='Edit Open to Work' i]")
        for _ in range(12):
            if btn.count():
                break
            pg.wait_for_timeout(700)
        if not btn.count():
            continue
        btn.first.click()
        for _ in range(10):
            pg.wait_for_timeout(700)
            if pg.evaluate(HUB_TEXT):
                print(f"  hub open (attempt {attempt + 1})")
                return True
    return False


def main() -> int:
    slug = (load_config("profile.yaml").get("identity", {})
            .get("linkedin", "https://www.linkedin.com/in/gerald-ofori-86b847169"))
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(slug, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(7000)

        if not open_hub(pg):
            print("hub never opened")
            pg.screenshot(path=str(SHOTS / "otw_nothub.png")); ctx.close(); return 2

        pg.locator("a[aria-label='Edit job preferences']").first.click()
        pg.wait_for_timeout(3000)
        if not pg.evaluate(FORM_DLG):
            print("job-preferences dialog not found")
            pg.screenshot(path=str(SHOTS / "otw_noform.png")); ctx.close(); return 3
        chips = pg.evaluate("""() => [...(window.__otwDialog||document).querySelectorAll('button')]
            .filter(b=>b.offsetParent).map(b=>(b.getAttribute('aria-label')||b.textContent.trim()).slice(0,26))""")
        print("chips/buttons:", json.dumps(chips))
        pg.screenshot(path=str(SHOTS / "otw_form.png"))
        if DRY:
            pg.keyboard.press("Escape"); ctx.close(); return 0

        print(f"[remove] {DROP}")
        removed = pg.evaluate("""(drop) => {
            const dlg = window.__otwDialog; if (!dlg) return false;
            const els = [...dlg.querySelectorAll('button,[role="button"],a,div')].filter(e => e.offsetParent);
            const pill = els.find(e => e.textContent.trim().toLowerCase() === drop.toLowerCase() &&
                (e.tagName !== 'DIV' || e.matches('[role="button"],button')));
            if (!pill) return false;
            const target = pill.querySelector('button,[role="button"]') || pill;
            ['pointerdown','mousedown','pointerup','mouseup','click']
                .forEach(t => target.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window})));
            return true;
        }""", DROP)
        print(f"  clicked chip: {removed}")
        pg.wait_for_timeout(1500)
        if not removed:
            print("  chip not found — aborting without save")
            pg.keyboard.press("Escape"); ctx.close(); return 4

        print(f"[add] {ADD}")
        added = False
        for _ in range(2):
            opened = pg.evaluate("""() => {
                const dlg = window.__otwDialog; if (!dlg) return false;
                const b = [...dlg.querySelectorAll('button,[role="button"]')].find(x => x.offsetParent &&
                    /add location|standort hinzufügen/i.test(x.textContent.trim()));
                if (!b) return false;
                ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t =>
                    b.dispatchEvent(new MouseEvent(t, {bubbles:true, cancelable:true, view:window})));
                return true;
            }""")
            if not opened:
                print("  no 'Add location' button"); break
            pg.wait_for_timeout(1500)
            iid = pg.evaluate("""() => {
                const dlg = window.__otwDialog || document;
                const el = [...dlg.querySelectorAll('input')].find(x => x.offsetParent &&
                    /^(text|search)$/i.test(x.type||'text'));
                return el ? el.id : null;
            }""")
            if not iid:
                print("  no location input appeared after clicking Add location")
                break
            el = pg.locator(f"#{iid}").first
            try:
                el.click(timeout=4000); el.type(ADD, delay=90)
            except Exception as e:
                print(f"  location input unusable: {str(e)[:60]}"); break
            for _ in range(6):
                pg.wait_for_timeout(800)
                got = pick_option(pg, ADD)
                if got:
                    print(f"  picked: {got!r}")
                    added = True
                    break
            if added:
                break
        if not added:
            print("  could not add location; closing without saving")
            pg.screenshot(path=str(SHOTS / "otw_addfail.png"))
            pg.keyboard.press("Escape"); ctx.close(); return 5

        pg.wait_for_timeout(1000)
        pg.screenshot(path=str(SHOTS / "otw_before_save.png"))
        saved = pg.evaluate("""() => {
            const dlg = window.__otwDialog; if (!dlg) return false;
            const b = [...dlg.querySelectorAll('button')].find(x => x.offsetParent &&
                /^(save|speichern|apply)$/i.test(x.textContent.trim()));
            if (!b) return false;
            b.click(); return true;
        }""")
        print(f"  saved: {saved}")
        pg.wait_for_timeout(4000)
        pg.screenshot(path=str(SHOTS / "otw_saved.png"))

        print("[verify]")
        pg.goto(slug, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        sd = pg.locator("text=/Show details/i")
        if sd.count():
            sd.first.click(); pg.wait_for_timeout(2200)
        print(pg.evaluate("""() => {
            const els = [...document.querySelectorAll('*')].filter(e => e.offsetParent &&
                /locations/i.test(e.innerText||'') && e.innerText.length < 400);
            els.sort((a,b)=>a.innerText.length-b.innerText.length);
            return els.length ? els[0].innerText.replace(/\\n+/g,' | ') : 'details not found';
        }"""))
        ctx.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())

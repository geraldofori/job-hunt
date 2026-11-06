"""Move the LinkedIn profile location to Chemnitz, Germany (country + city).

The 'Edit intro' form is inline on the profile page (not a role=dialog modal)
and its inputs have generated ids, so everything here is addressed by
aria-label. Changing the country can force a postal code, which we fill with
TU Chemnitz's code. Screenshots each stage under logs/setup/.

Usage: venv/bin/python scripts/linkedin_location.py
"""
from __future__ import annotations

import sys

from playwright.sync_api import sync_playwright

from common import ROOT, load_config

CITY, COUNTRY, POSTAL = "Chemnitz", "Germany", "09126"
SHOTS = ROOT / "logs" / "setup"
SHOTS.mkdir(parents=True, exist_ok=True)


def shot(pg, name: str) -> None:
    try:
        pg.screenshot(path=str(SHOTS / f"loc_{name}.png"))
    except Exception as e:
        print(f"  [shot failed] {name}: {e}")


def open_intro_editor(pg) -> bool:
    pg.locator("a[aria-label='Edit profile']").first.click()
    for _ in range(20):
        if pg.locator("input[aria-label='Country/Region']").count():
            return True
        pg.wait_for_timeout(500)
    return False


def read_value(pg, aria: str):
    """Value of input[aria-label=aria] via JS — locators here go stale as
    LinkedIn re-renders, and input_value() would wait 30s on a detached node."""
    return pg.evaluate("""(a) => {
        const e = document.querySelector(`input[aria-label="${a}"]`);
        return e ? (e.value || "") : null;
    }""", aria)


def input_id_by_label(pg, text: str):
    """LinkedIn's postal-code input has no aria-label; find it through its
    <label for=...> instead."""
    return pg.evaluate("""(t) => {
        const lab = [...document.querySelectorAll('label')]
            .find(l => l.textContent.trim().toLowerCase().includes(t));
        return lab && lab.htmlFor ? lab.htmlFor : null;
    }""", text.lower())


def pick_option(pg, expect: str):
    """Click a typeahead suggestion via JS (Playwright's actionability checks
    reject LinkedIn's portal-rendered options)."""
    return pg.evaluate("""(exp) => {
        const opts = [...document.querySelectorAll("[role='option'], li[role='option'], .artdeco-typeahead__result")];
        const hit = opts.find(o => ((o.textContent||'').toLowerCase().includes(exp)) && o.offsetWidth > 0);
        if (!hit) return null;
        hit.click();
        return (hit.textContent||'').trim().slice(0,48);
    }""", expect.lower())


def typeahead(pg, aria: str, text: str, expect: str) -> bool:
    el = pg.locator(f"input[aria-label='{aria}']")
    if not el.count():
        print(f"  no input[aria-label={aria!r}]")
        return False
    el.first.click()
    el.first.fill("")
    el.first.type(text, delay=80)
    picked = None
    for attempt in range(5):
        pg.wait_for_timeout(900)
        picked = pick_option(pg, expect)
        if picked:
            print(f"  {aria}: picked {picked!r}")
            break
    if not picked:
        print(f"  {aria}: no option matched {expect!r}; trying ArrowDown+Enter")
        el.first.press("ArrowDown"); pg.wait_for_timeout(400); el.first.press("Enter")
    pg.wait_for_timeout(1200)
    val = read_value(pg, aria) or ""
    print(f"  {aria} now: {val!r}")
    return expect.lower() in val.lower()


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
        pg.wait_for_timeout(6000)

        if not open_intro_editor(pg):
            print("intro editor never showed its fields")
            shot(pg, "no_editor")
            ctx.close()
            return 2
        shot(pg, "01_editor")
        print(f"  before: country={read_value(pg, 'Country/Region')!r} city={read_value(pg, 'City')!r}")

        cur_country = read_value(pg, "Country/Region") or ""
        if COUNTRY.lower() in cur_country.lower():
            print(f"[1] country already {COUNTRY}")
        elif not typeahead(pg, "Country/Region", COUNTRY[:4], COUNTRY):
            print("  country typeahead failed"); shot(pg, "country_fail"); ctx.close(); return 3
        pg.wait_for_timeout(1500)

        # Germany infers City from the postal code. The postal input carries no
        # aria-label, so resolve it by its <label for=...>.
        pid = None
        for _ in range(16):
            pid = input_id_by_label(pg, "postal")
            if pid:
                break
            pg.wait_for_timeout(500)
        if pid:
            try:
                pel = pg.locator(f"#{pid}")
                pel.scroll_into_view_if_needed(timeout=3000)
                pel.click(timeout=5000)
                pel.fill(POSTAL)
                pel.press("Tab")
                print(f"  postal code -> {POSTAL} (input #{pid})")
            except Exception as e:
                print(f"  postal fill failed: {e}")
            pg.wait_for_timeout(2000)
        else:
            print("  no postal input found")
        city_val = read_value(pg, "City")
        if city_val is not None and not city_val.strip():
            print(f"[2] city -> {CITY}")
            if not typeahead(pg, "City", CITY, CITY):
                print("  city typeahead failed"); shot(pg, "city_fail"); ctx.close(); return 4
        elif city_val:
            print(f"[2] city already set: {city_val!r}")
        else:
            print("[2] no separate city field (postal code covers it)")
        pg.wait_for_timeout(1000)
        print("  form state:", pg.evaluate("""() => [...document.querySelectorAll('input')].filter(e=>e.offsetWidth>0).map(e=>{
            let l=e.getAttribute('aria-label')||(e.labels&&e.labels[0]&&e.labels[0].textContent.trim());
            return l? l+'='+JSON.stringify((e.value||'').slice(0,28)) : null;
          }).filter(Boolean)"""))
        shot(pg, "02_filled")

        for sel in ("button:has-text('Save')", "button[aria-label*='Save' i]",
                    "button:has-text('Speichern')"):
            btn = pg.locator(sel)
            if btn.count() and btn.first.is_visible():
                btn.first.click(); print(f"  saved via {sel}"); break
        else:
            print("  no Save button found"); shot(pg, "no_save"); ctx.close(); return 5
        pg.wait_for_timeout(5000)
        shot(pg, "03_saved")

        print("[3] verify")
        pg.goto(slug, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        body = pg.inner_text("body")
        ok = CITY.lower() in body.lower()
        lines = [l.strip() for l in body.splitlines()
                 if CITY.lower() in l.lower() or "accra" in l.lower() or "ghana" in l.lower()]
        print(f"  Chemnitz visible: {ok}")
        print("  lines:", lines[:5])
        shot(pg, "04_verify")
        ctx.close()
        return 0 if ok else 6


if __name__ == "__main__":
    sys.exit(main())

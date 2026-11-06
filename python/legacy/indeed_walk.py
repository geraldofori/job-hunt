"""Walk the Indeed apply wizard (step-by-step exploration).

Loads a job, clicks 'Schnellbewerbung', then iteratively:
  * prints the current step (URL + headings + visible fields),
  * clicks the primary 'Weiter' control,
  * screenshots, until a submit/review step or no Weiter remains.

Usage: venv/bin/python scripts/indeed_walk.py [jk] [--max N]
"""
from __future__ import annotations

import json
import sys

from playwright.sync_api import sync_playwright

from common import ROOT

JK = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "b804c4497a600281"
MAX_STEPS = 12
for a in sys.argv:
    if a.startswith("--max"):
        MAX_STEPS = int(a.split("=")[1]) if "=" in a else 12
SHOTS = ROOT / "logs" / "setup"


def frame_for(pg):
    """SmartApply renders either in an iframe or as the main document."""
    for f in pg.frames:
        u = f.url or ""
        if "smartapply" in u and "/form/" in u:
            try:
                if f.evaluate("() => !!document.querySelector('button, input')"):
                    return f
            except Exception:
                continue
    return pg.main_frame


def step_info(fr):
    return fr.evaluate("""() => ({
        url: location.href.slice(0, 110),
        h: [...document.querySelectorAll('h1,h2,h3,[role=heading]')].filter(e=>e.offsetParent)
           .map(e=>e.textContent.trim().slice(0,60)).slice(0,5),
        fields: [...document.querySelectorAll('input,select,textarea')].filter(e=>e.offsetParent||e.tagName==='SELECT')
           .map(e=>({t:e.tagName, ty:e.type||null, aria:(e.getAttribute('aria-label')||'').slice(0,36),
                     lab:(e.labels&&e.labels[0]?e.labels[0].textContent.trim().slice(0,36):''),
                     val:(e.value||'').slice(0,30), req:e.required}))
           .slice(0,12),
        btns: [...document.querySelectorAll('button')].filter(e=>e.offsetParent)
           .map(e=>(e.getAttribute('aria-label')||e.textContent||'').trim().slice(0,34)).filter(Boolean).slice(0,10),
        progress: (document.body.innerText.match(/\\d+\\s*%/g)||[]).slice(0,3),
    })""")


def click_weiter(fr) -> bool:
    return fr.evaluate("""() => {
        const pref = /^(weiter|continue|next|weiter mit|zum nächsten|fortfahren)$/i;
        const els = [...document.querySelectorAll('button,[role=button],a')].filter(e => e.offsetParent);
        // prefer a bottom-of-form primary action; skip 'Weiter zur Übersicht'
        const cands = els.filter(e => !/übersicht|overview/i.test((e.textContent||'').trim()) &&
            pref.test((e.textContent||'').trim()));
        if (cands.length) { cands[cands.length - 1].click(); return true; }
        return false;
    }""")


def main() -> int:
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        pg.goto(f"https://de.indeed.com/viewjob?jk={JK}", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        opened = pg.evaluate("""() => { const b=[...document.querySelectorAll('a,button')].find(x=>x.offsetParent&&
            /schnellbewerbung|quick apply|easily apply|jetzt bewerben/i.test((x.textContent||'').trim()));
            if(!b) return false; b.click(); return true; }""")
        print("apply clicked:", opened)
        pg.wait_for_timeout(12000)

        seen = set()
        for i in range(MAX_STEPS):
            fr = frame_for(pg)
            try:
                info = step_info(fr)
            except Exception as e:
                print("step err:", str(e)[:60]); break
            print(f"\n=== step {i} @ {info['url']}")
            print("  headings:", info["h"][:3])
            print("  progress:", info["progress"])
            for f in info["fields"]:
                print("  field:", json.dumps(f, ensure_ascii=False))
            print("  buttons:", info["btns"][:8])
            pg.screenshot(path=str(SHOTS / f"walk_{i:02d}.png"))
            key = info["url"]
            if key in seen:
                print("  same URL twice — stopping (fields need answers or it's the review)")
                break
            seen.add(key)
            if not click_weiter(fr):
                print("  no Weiter — reached end/review")
                break
            pg.wait_for_timeout(9000)
        ctx.close()
        return 0


if __name__ == "__main__":
    sys.exit(main())

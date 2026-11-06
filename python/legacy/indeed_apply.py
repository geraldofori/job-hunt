"""Indeed 'Schnellbewerbung' (Easy Apply) engine.

Walks the SmartApply wizard for one job and answers each step from
config/profile.yaml:
  * resume-selection: upload/choose Gerald_Ofori_Lebenslauf.pdf
  * contact-info:     names/phone from profile
  * questions/N:      label-driven answers (email, location, availability,
                      salary, residency, work authorization, ...)
  * review:           submit when --submit is given, otherwise stop and report

Safety: any required question we cannot answer cleanly aborts the run
(needs_manual) with the page left open — never guesses.

Usage: venv/bin/python scripts/indeed_apply.py <jk|job_url> [--submit]
"""
from __future__ import annotations

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

from apply_engine import _resolve_start_date
from common import ROOT, get_logger, load_config

log = get_logger("indeed")
SUBMIT = "--submit" in sys.argv
TARGET = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else ""
CV = ROOT / load_config("profile.yaml")["documents"]["cv_pdf"]


def local_phone(profile: dict) -> str:
    digits = "".join(c for c in profile["identity"]["phone"] if c.isdigit())
    return digits[2:] if digits.startswith("49") else digits


class IndeedApply:
    def __init__(self, pg, profile: dict):
        self.pg = pg
        self.profile = profile
        self.unknown: list[str] = []

    # ---- frame helpers ----
    def form_frame(self):
        for f in self.pg.frames:
            if "smartapply" in (f.url or "") and "/form/" in (f.url or ""):
                try:
                    if f.evaluate("() => !!document.querySelector('button,input,textarea,select')"):
                        return f
                except Exception:
                    pass
        return self.pg.main_frame

    def fields(self, fr) -> list[dict]:
        return fr.evaluate("""() => [...document.querySelectorAll('input,select,textarea')]
            .filter(e => e.offsetParent || e.tagName === 'SELECT')
            .map(e => ({ tag: e.tagName, ty: e.type || null, id: e.id || null,
                         lab: (e.labels && e.labels[0] ? e.labels[0].textContent.trim() : ''),
                         aria: e.getAttribute('aria-label') || '',
                         val: (e.value || '').slice(0, 40),
                         req: e.required || e.getAttribute('aria-required') === 'true' }))""")

    def question_blocks(self, fr) -> list[dict]:
        """Question text + its controls, so answers can be label-driven."""
        return fr.evaluate("""() => {
            const out = [];
            const ctrls = [...document.querySelectorAll('input,select,textarea')].filter(e =>
                e.offsetParent || e.tagName === 'SELECT');
            for (const c of ctrls) {
                let q = '';
                if (c.labels && c.labels.length) q = c.labels[0].textContent.trim();
                if (!q) { let n = c; for (let k = 0; k < 6 && n; k++) { n = n.parentElement;
                    if (n && n.innerText && n.innerText.length > q.length) q = n.innerText.trim().split('\\n')[0];
                    if (q && q.length > 90) break; } }
                out.push({ id: c.id || null, tag: c.tagName, ty: c.type || null, q: q.slice(0, 120),
                           aria: c.getAttribute('aria-label') || '',
                           val: (c.value || '').slice(0, 40),
                           req: c.required || c.getAttribute('aria-required') === 'true',
                           opts: [...(c.closest('[role=radiogroup],[role=group],fieldset')?.querySelectorAll('label') || [])]
                                  .map(l => l.textContent.trim().slice(0, 70)).slice(0, 6) });
            }
            return out;
        }""")

    def click_control(self, fr, fid: str, value: str | None = None, force: str = "") -> bool:
        return fr.evaluate("""({ fid, value, force }) => {
            const el = document.querySelector(`[id="${CSS.escape ? fid : fid}"]`) ||
                       document.getElementById(fid);
            if (!el) return false;
            if (force === 'check') { el.click(); return true; }
            el.focus();
            if (value !== null && value !== undefined) {
                const setter = Object.getOwnPropertyDescriptor(
                    el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype, 'value');
                setter.set.call(el, value);
                el.dispatchEvent(new Event('input', { bubbles: true }));
                el.dispatchEvent(new Event('change', { bubbles: true }));
                el.dispatchEvent(new Event('blur', { bubbles: true }));
            }
            return true;
        }""", {"fid": fid, "value": value, "force": force})

    # ---- answering ----
    def answer(self, blk: dict) -> str | None:
        p = self.profile
        ident, sa = p["identity"], p.get("screening_answers", {})
        q = (blk["q"] + " " + blk.get("aria", "")).lower()
        if blk["tag"] == "SELECT":
            return None
        if blk["ty"] == "radio":
            opts = " ".join(o.lower() for o in blk["opts"])
            optset = {o.strip().lower() for o in blk["opts"]}
            # 'Gender *' renders the required flag on the group, not on inputs;
            # identify it by its option set instead.
            if {"male", "female"} <= optset:
                return ("pick_label", "Male")
            if re.search(r"already live|lebe ich (schon|bereits)|in deutschland", q + " " + opts):
                for o in blk["opts"]:
                    if re.search(r"yes,? i already live|ja, ich lebe bereits", o.lower()):
                        return ("pick_label", o[:70])
            auth = (sa.get("work_authorization") or "").lower()
            if re.search(r"(authorized|berechtigt).*(work|arbeit)|work permit|arbeitserlaubnis", q):
                want = "yes" if auth.startswith("yes") else "no"
                for o in blk["opts"]:
                    if o.lower().startswith(want):
                        return ("pick_label", o[:70])
            if re.search(r"gender|geschlecht", q) and blk["req"]:
                return ("pick_label", "Male")
            return None
        if blk["tag"] == "TEXTAREA":
            if re.search(r"zusatz|additional|why|motivation|cover", q):
                return ("fill", None)  # optional: skip
            return None
        # text inputs
        if re.search(r"^\s*(e-?mail)", q):
            return ("fill", ident["email"])
        if re.search(r"vorname|first name", q):
            return ("fill", ident["first_name"])
        if re.search(r"nachname|last name|surname", q):
            return ("fill", ident["last_name"])
        if re.search(r"telefon|phone", q):
            return ("fill", local_phone(p))
        if re.search(r"\blocation\b|standort|ort", q):
            return ("fill", f"{ident['city']}, {ident['country']}")
        if re.search(r"available (from)?|start date|frühstens|eintritt|ab wann", q):
            iso = _resolve_start_date(self.profile) or ""
            m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso)
            return ("fill", f"{m.group(3)}.{m.group(2)}.{m.group(1)}" if m else iso)
        if re.search(r"salary|gehalt|vergütung", q):
            return ("fill", sa.get("salary_expectation", ""))
        return None

    def answer_step(self, fr) -> None:
        for blk in self.question_blocks(fr):
            if not blk["id"]:
                continue
            qtxt = (blk["q"] + " " + blk.get("aria", "")).lower()
            force_refill = bool(re.search(r"phone|telefon|e-?mail|location|standort", qtxt))
            if blk["val"].strip() and blk["ty"] != "radio" and not force_refill:
                continue
            ans = self.answer(blk)
            if ans is None:
                if blk["req"]:
                    self.unknown.append(f"{blk['q'][:60]!r} ({blk['ty'] or blk['tag']})")
                continue
            kind, val = ans
            if kind == "pick_label":
                got = fr.evaluate("""(label) => {
                    const labs = [...document.querySelectorAll('label')].filter(l =>
                        l.offsetParent && l.textContent.trim().toLowerCase().startsWith(label.toLowerCase()));
                    if (!labs.length) return false;
                    (labs[0].htmlFor ? document.getElementById(labs[0].htmlFor) : labs[0]).click();
                    return true;
                }""", val)
                log.info("radio %-40s -> %s (%s)", blk["q"][:40], val[:26], got)
            else:
                if val is None:
                    continue
                ok = self.click_control(fr, blk["id"], value=val)
                log.info("fill %-40s -> %-28s (%s)", blk["q"][:40], val[:28], ok)
                if not ok and blk["req"]:
                    self.unknown.append(f"could not fill {blk['q'][:40]!r}")

    def click_next(self, fr) -> bool:
        return fr.evaluate("""() => {
            const els = [...document.querySelectorAll('button,[role=button]')].filter(e => e.offsetParent);
            const next = els.filter(e => /^(weiter|continue|next)$/i.test((e.textContent || '').trim())
                && !/übersicht/i.test(e.textContent || ''));
            if (next.length) { next[next.length - 1].click(); return true; }
            return false;
        }""")

    def resume_step(self, fr) -> None:
        # upload our CV if the profile does not already carry it
        if not fr.evaluate("""(name) => document.body.innerText.includes(name)""", CV.name):
            fi = fr.locator("input[type='file']")
            if fi.count():
                fi.first.set_input_files(str(CV))
                log.info("uploaded resume %s", CV.name)
                self.pg.wait_for_timeout(6000)
        fr.evaluate("""(name) => {
            const labs = [...document.querySelectorAll('label')].filter(l => l.textContent.includes(name));
            if (!labs.length) return false;
            const r = labs[0].htmlFor ? document.getElementById(labs[0].htmlFor)
                : labs[0].closest('div')?.querySelector('input[type=radio]');
            if (r) r.click();
            return !!r;
        }""", CV.name)

    def submit_if_review(self, fr) -> bool:
        # Headings only: the resume PREVIEW text can contain 'review' (e.g.
        # "code reviews") and fool a whole-body match.
        is_review = fr.evaluate("""() => {
            const hs = [...document.querySelectorAll('h1,h2,h3,[role=heading]')]
                .map(h => (h.textContent || '').trim().toLowerCase());
            return hs.some(t => /überprüfen|zusammenfassung|review your|application review/.test(t));
        }""")
        if not is_review:
            return False
        self.pg.screenshot(path=str(ROOT / "logs" / "review_before_submit.png"), full_page=True)
        if not SUBMIT:
            log.info("review page reached — not submitting (no --submit)")
            return True
        done = fr.evaluate("""() => {
            const els = [...document.querySelectorAll('button')].filter(e => e.offsetParent);
            const b = els.find(e => /send application|bewerbung (absenden|senden)|apply now|jetzt bewerben/i
                .test((e.textContent || '').trim()));
            if (!b) return false;
            b.click(); return true;
        }""")
        log.info("submit clicked: %s", done)
        return done


def main() -> int:
    if not TARGET:
        print("usage: indeed_apply.py <jk or job_url> [--submit]"); return 1
    url = TARGET if TARGET.startswith("http") else f"https://de.indeed.com/viewjob?jk={TARGET}"
    profile = load_config("profile.yaml")
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            str(ROOT / "browser-profile"), headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1440, "height": 900})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        eng = IndeedApply(pg, profile)
        pg.goto(url, wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(6000)
        clicked = pg.evaluate("""() => { const b = [...document.querySelectorAll('a,button')].find(x => x.offsetParent &&
            /schnellbewerbung|quick apply|easily apply|jetzt bewerben/i.test((x.textContent || '').trim()));
            if (!b) return false; b.click(); return true; }""")
        if not clicked:
            print("no apply button (job closed or external?)"); ctx.close(); return 2
        pg.wait_for_timeout(10000)

        last = ""
        for step in range(14):
            fr = eng.form_frame()
            try:
                slug = re.sub(r".*/form/", "", fr.url or "")[:46]
            except Exception:
                slug = "main"
            if "resume-selection" in slug:
                eng.resume_step(fr)
            else:
                eng.answer_step(fr)
                if eng.unknown:
                    log.warning("unanswered required: %s", eng.unknown)
                    pg.screenshot(path=str(ROOT / "logs" / f"indeed_unknown_{step}.png"))
                    print("NEEDS_MANUAL — leaving browser open")
                    return 3
            if eng.submit_if_review(fr):
                break
            if not eng.click_next(fr):
                print("no Weiter — at review or blocked")
                pg.screenshot(path=str(ROOT / "logs" / f"indeed_end_{step}.png"))
                break
            pg.wait_for_timeout(7000)
            if slug == last and step > 2:
                print("stuck on same step; screenshot saved")
                pg.screenshot(path=str(ROOT / "logs" / f"indeed_stuck_{step}.png"))
                return 4
            last = slug
        pg.wait_for_timeout(4000)
        pg.screenshot(path=str(ROOT / "logs" / "indeed_final.png"))
        body = pg.inner_text("body").lower()
        ok = any(k in body for k in ("application submitted", "bewerbung gesendet",
                                     "successfully submitted", "vielen dank"))
        print("SUBMITTED" if (SUBMIT and ok) else "stopped at wizard (see logs/indeed_final.png)")
        ctx.close()
        return 0 if ok else 5


if __name__ == "__main__":
    sys.exit(main())

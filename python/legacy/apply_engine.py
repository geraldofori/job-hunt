"""Application submission engine.

Uses ONE persistent Chromium profile (browser-profile/) so every site session
(LinkedIn, Indeed, Gmail, company portals) survives across runs.

LinkedIn Easy Apply is walked automatically; unknown REQUIRED questions abort
the application cleanly (modal closed, job marked needs_manual) instead of
submitting wrong answers. External portals are opened for manual approval.
"""
from __future__ import annotations

import json
import random
import re
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import BrowserContext, Page, sync_playwright

from common import BROWSER_PROFILE, LOGS, get_logger, load_config

log = get_logger("apply")

ACCOUNTS_REGISTRY = Path(__file__).resolve().parent.parent / "data" / "accounts.json"


def human_pause(a: float = 1.2, b: float = 3.5) -> None:
    time.sleep(random.uniform(a, b))


def open_browser(headless: bool = False) -> tuple[sync_playwright, BrowserContext]:
    pw = sync_playwright().start()
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(BROWSER_PROFILE),
        headless=headless,
        slow_mo=random.randint(60, 140),
        viewport={"width": 1360, "height": 900},
        locale="en-US",
        args=["--disable-blink-features=AutomationControlled"],
    )
    return pw, ctx


# ------------------------------------------------------------------ helpers
LABEL_ANSWERS = [
    # (regex on label/question, profile path or literal) — checked in order
    (r"country code|vorwahl|ländervorwahl|laendervorwahl", "phone_country"),
    (r"handy|mobil|phone|telefon", "phone"),
    (r"e-?mail", "email"),
    (r"first ?name|vorname", "first_name"),
    (r"last ?name|surname|nachname|familienname", "last_name"),
    (r"full ?name", "full_name"),
    (r"city|standort|wohnort|address|adresse", "city_country"),
    (r"linkedin", "linkedin"),
    (r"github", "github"),
    (r"website|portfolio", "website"),
]

IDENTITY_FIELDS = {
    "first_name", "last_name", "full_name", "email", "phone", "phone_country",
    "city_country", "linkedin", "github", "website",
}

SCREENING_PATTERNS = [
    (r"(authorized|berechtigt).{0,40}(work|arbeiten)|work permit|arbeitserlaubnis",
     "screening_answers.work_authorization"),
    (r"enrolled|immatrikul|student|studier", "screening_answers.enrollment_status"),
    (r"studium zu beenden|end of.{0,20}stud|expected graduation|"
     r"graduation|abschluss|when.{0,20}(finish|complete)", "screening_answers.study_end"),
(r"hours? per week|stunden pro woche|wochenstunden|availability|verfügbarkeit",
     "screening_answers.availability_hours"),
    (r"\bstart\b|early ?start|earliest|frühst|ab wann|eintritt|beginn|anfang|"
     r"when.*(start|join)|sofort", "screening_answers.earliest_start"),
    (r"annual|jährlich|yearly|jahres.{0,14}(gehalt|einkommen|erwartung)|"
     r"gehalt.{0,14}jährlich", "screening_answers.salary_expectation_annual"),
    (r"monatlich|pro\s*monat|monthly|per\s*month|monats(einkommen|gehalt|betrag)",
     "screening_answers.salary_expectation_monthly"),
    (r"stündlich|pro\s*stunde|hourly|per\s*hour|stundenlohn",
     "screening_answers.salary_expectation"),
    (r"salary|gehalt|vergütung|stundenlohn", "screening_answers.salary_expectation"),
    (r"german|deutsch", "screening_answers.german_level"),
    (r"relocat|umzug", "screening_answers.relocation"),
    (r"notice|kündigungsfrist", "screening_answers.notice_period"),
]


def resolve_profile_value(profile: dict, dotted: str) -> str:
    if dotted == "city_country":
        return f"{profile['identity']['city']}, {profile['identity']['country']}"
    if dotted == "phone_country":
        return phone_parts(profile)[0]
    if dotted in IDENTITY_FIELDS:
        dotted = f"identity.{dotted}"
    node = profile
    for part in dotted.split("."):
        node = node[part]
    return str(node)


def phone_parts(profile: dict) -> tuple[str, str]:
    """Split +49 1590 7981322 -> ('+49', '1590 7981322')."""
    raw = str(profile["identity"]["phone"]).strip()
    m = re.match(r"(\+\d{1,3})[\s]*(.+)", raw)
    if m:
        return m.group(1), m.group(2).strip()
    return "", raw


def set_country_combobox(el, code: str) -> bool:
    """LinkedIn's country code is a searchable combobox."""
    try:
        el.click()
        el.type(code, delay=60)
        time.sleep(0.8)
        el.press("Enter")
        time.sleep(0.4)
        return True
    except Exception:
        return False


def pick_country_option(profile: dict, options: list[str]) -> str | None:
    """Choose the option matching the profile phone country code."""
    code = phone_parts(profile)[0]  # e.g. +49
    # exact code match: "Germany (+49)"
    for opt in options:
        if re.search(rf"\({re.escape(code)}\)", opt):
            return opt.strip()
    # country-name match
    country = profile["identity"].get("country", "")
    country_de = profile["identity"].get("country_de", country)
    for opt in options:
        low = opt.lower()
        if country and country.lower() in low:
            return opt.strip()
        if country_de and country_de.lower() in low:
            return opt.strip()
    return None


def select_option_safe(el, value: str | None = None, label: str | None = None) -> bool:
    """React ignores a raw `el.value = x`, so use Playwright's native setter first."""
    if value is not None:
        try:
            el.select_option(value=value, timeout=4000)
            return True
        except Exception:
            pass
    if label is not None:
        try:
            el.select_option(label=label, timeout=4000)
            return True
        except Exception:
            pass
    # last resort: native value setter + input/change events
    try:
        return bool(el.evaluate(
            """(el, value) => {
                const opt = [...el.options].find(o => o.value === value || o.text === value);
                if (!opt) return false;
                const setter = Object.getOwnPropertyDescriptor(
                    HTMLSelectElement.prototype, 'value').set;
                setter.call(el, opt.value);
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
                return el.value === opt.value;
            }""", value or label))
    except Exception:
        return False


RTL_CHARS = "\u200e\u200f\u061c"


def clean_text(s: str) -> str:
    """Strip RTL control marks LinkedIn injects into non-Latin UIs."""
    return (s or "").translate({ord(c): None for c in RTL_CHARS}).strip()


def ui_locale_looks_wrong(page: Page) -> bool:
    txt = page.evaluate("() => (document.body.innerText || '').slice(0, 800)") or ""
    return bool(re.search(r"[\u0600-\u06FF\u0750-\u077F\u0980-\u09FF]", txt))


def force_ui_locale(page: Page, value: str = "en_US") -> bool:
    """LinkedIn's footer language <select> rewrites the entire UI. Put it back."""
    try:
        return bool(page.evaluate(
            """(value) => {
                const s = [...document.querySelectorAll('select')].find(x =>
                    [...x.options].some(o => /\\(English\\)/.test(o.text)
                                       || /\\(Deutsch\\)/.test(o.text)));
                if (!s) return false;
                const o = [...s.options].find(x => x.value === value)
                       || [...s.options].find(x => /English/.test(x.text));
                if (!o) return false;
                s.value = o.value;
                s.dispatchEvent(new Event('input', {bubbles: true}));
                s.dispatchEvent(new Event('change', {bubbles: true}));
                return true;
            }""", value))
    except Exception:
        return False


NEXT_WORDS = ("Next", "Weiter", "Fortfahren", "Suivant", "Siguiente", "Avanti", "Volgende")
REVIEW_WORDS = ("Review", "Überprüfen", "Ueberpruefen", "Révision")
SUBMIT_WORDS = ("Submit application", "Bewerbung absenden", "Bewerbung abschicken",
                "Submit", "Bewerbung senden", "Envoyer", "Enviar")
EASY_APPLY_WORDS = ("Easy Apply", "Schnellbewerbung", "Bewerbung", "easy apply")


def pick_text(page: Page, words, prefer_last: bool = True):
    """Return the first visible button whose text matches any of `words`."""
    buttons = page.locator("button:visible, [role='button']:visible")
    for w in words:
        loc = page.locator(f"button:visible:has-text('{w}'), [role='button']:visible:has-text('{w}')")
        n = loc.count()
        if n:
            return loc.nth(n - 1) if prefer_last else loc.first
    return None


LABEL_JS = """el => {
    const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
    const controls = n => !!(n && n.querySelectorAll)
        ? n.querySelectorAll('input:not([type=hidden]), select, textarea').length : 0;

    // 1) the label that explicitly belongs to THIS control
    if (el.id) {
        const l = document.querySelector(`label[for="${el.id}"]`);
        if (l && clean(l.innerText)) return clean(l.innerText);
    }
    const own = clean(el.getAttribute('aria-label')) || clean(el.placeholder);
    if (own) return own;

    // 2) climb only while the ancestor still owns exactly one control, so we
    //    can never inherit a sibling field's question
    let n = el;
    for (let i = 0; i < 6 && n; i++, n = n.parentElement) {
        if (controls(n) !== 1) break;
        const l = n.querySelector('label') || n.querySelector('legend');
        const t = clean(l && l.innerText);
        if (t && t.length < 220) return t;
        const aria = clean(n.getAttribute('aria-label'));
        if (aria) return aria;
    }

    // 3) componentkey wrapper that owns exactly this one control
    n = el;
    for (let i = 0; i < 6 && n; i++, n = n.parentElement) {
        if (n.getAttribute && n.getAttribute('componentkey') && controls(n) === 1) {
            const t = clean(n.innerText)
                .replace(/\\d+\\s*\\/\\s*\\d+\\s*(characters?|zeichen)?/gi, '').trim();
            if (t) return t.slice(0, 160);
        }
    }
    return '';
}"""

# Option label for a radio/checkbox: its OWN text, never the question.
# LinkedIn puts the question in a <label> attached to the radio AND the short
# option text in a wrapper further up — so collect candidates and keep the
# SHORTEST non-empty one ("Ja", "Nein"), which is always the option itself.
OPTION_JS = """el => {
    const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
    const cands = [];
    if (el.labels && el.labels.length)
        el.labels.forEach(l => { const t = clean(l.innerText); if (t) cands.push(t); });
    const aria = clean(el.getAttribute('aria-label'));
    if (aria) cands.push(aria);
    let n = el.parentElement;
    for (let i = 0; i < 4 && n; i++, n = n.parentElement) {
        const t = clean(n.innerText);
        if (t) {
            if (t.length < 40) { cands.push(t); break; }
            if (t.length >= 40) break;
        }
    }
    cands.sort((a, b) => a.length - b.length);
    return cands.length ? cands[0] : '';
}"""

GROUP_QUESTION_JS = """fs => {
    const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
    const lg = fs.querySelector('legend');
    if (lg && clean(lg.innerText)) return clean(lg.innerText).slice(0, 200);
    const opts = [...fs.querySelectorAll('input')]
        .map(i => { let n = i;
            for (let k = 0; k < 5 && n; k++, n = n.parentElement) {
                const t = clean(n.innerText);
                if (t && t.length < 40) return t;
                if (t && t.length >= 40) break;
            } return ''; })
        .filter(Boolean);
    let n = fs, last = '';
    for (let i = 0; i < 6 && n; i++, n = n.parentElement) {
        let t = clean(n.innerText);
        if (!t) continue;
        for (const o of opts) t = t.replace(o, ' ');
        t = clean(t);
        if (t && t.length < 220) return t;
        if (t) last = t.slice(0, 160);
    }
    return last;
}"""

# LinkedIn asks proficiency in two shapes: a CEFR scale ("A1 - Anfänger*in" …
# "C2 - muttersprachlich") and a 4-step scale ("Gar nicht" … "Muttersprache").
# Scores are comparable so one matcher serves both.
LEVEL_SCORES = [
    (r"gar nicht|keine kenntnisse|\bnone\b", 1),
    (r"\ba1\b|anfänger|beginner|^gut$|conversation", 2),
    (r"\ba2\b|grundkenntnisse\s*$|elementary", 3),
    (r"\bb1\b|verhandlungssicher|professional", 4),
    (r"\bb2\b|fortgeschritten", 5),
    (r"\bc1\b|nahezu", 6),
    (r"\bc2\b|muttersprach|native", 7),
]
LEVEL_TARGET = {"german": 2, "english": 7}   # A1 (weakest truthful) / native
RADIO_GROUPS_JS = """() => {
    const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
    const optText = el => {
        let n = el.parentElement;
        for (let i = 0; i < 4 && n; i++, n = n.parentElement) {
            const t = clean(n.innerText);
            if (t && t.length < 40) return t;
            if (t && t.length >= 40) break;
        }
        const l = el.labels && el.labels.length ? clean(el.labels[0].innerText) : '';
        return l.length < 40 ? l : '';
    };
    const seen = new Set(); const out = [];
    document.querySelectorAll('input[type=radio]').forEach(r => {
        if (!r.offsetParent) return;
        const key = r.name || (r.closest('fieldset')?.id) || r.id;
        if (seen.has(key)) return; seen.add(key);
        const members = r.name
            ? [...document.querySelectorAll(`input[type=radio][name="${r.name}"]`)]
                .filter(x => x.offsetParent)
            : [r];
        const opts = members.map(optText).filter(Boolean);
        const qFromLabels = r.labels?.length ? clean(r.labels[0].innerText) : '';
        let q = '';
        const fs = r.closest('fieldset');
        if (fs) { const lg = fs.querySelector('legend'); q = clean(lg?.innerText); }
        if (!q) q = qFromLabels;
        // the question often sits ABOVE the group — climb until we find text
        // that is more than just the option words
        let n = r.parentElement;
        for (let i = 0; i < 8 && n; i++, n = n.parentElement) {
            const t = clean(n.innerText);
            if (!t) continue;
            let rest = t;
            for (const o of opts) rest = rest.split(o).join(' ');
            rest = clean(rest);
            if (rest && rest.length > q.length && rest.length < 260) q = rest;
            if (rest && rest.length >= 260) break;
        }
        const blob = (n ? clean(n.innerText) : '') || clean(fs?.parentElement?.innerText || '');
        const anyChecked = members.some(m => m.checked);
        const req = members.some(m => m.required) || /\\*/.test(q)
                 || /required|erforderlich/i.test(blob);
        out.push({ name: r.name || '', ids: members.map(m => m.id),
                   checked: anyChecked, required: !!req, question: q, opts });
    });
    return out;
}"""

LEVEL_SELECT_PATTERNS = {
    "german": r"german|deutsch",
    "english": r"english|englisch",
}
YES_NO = {"yes": ("ja", "yes", "y"), "no": ("nein", "no", "n")}
YES_NO_QUESTION_PATTERNS = [
    (r"immatrikul|enrolled|registrier|study|studier|student|ausbildung|"
     r"authorized|berechtigt|eligible|verf[üu]gbar|available|start|frei", "yes"),
    (r"sponsor|visa|relocat|umzug|vorbelastet|leased", "no"),
]


def _level_score(text: str) -> int | None:
    t = clean_text(text).lower()
    for pat, score in LEVEL_SCORES:
        if re.search(pat, t):
            return score
    return None


def answer_level_select(profile: dict, question: str,
                        opts: list[tuple[str, str]]) -> str | None:
    """Return the option TEXT to select for a required dropdown, or None."""
    q = clean_text(question).lower()
    labels = [clean_text(t) for _, t in opts if clean_text(t)
              and not re.match(r"^(select|bitte|choose|please select)",
                               clean_text(t), re.I)]

    # 1) yes/no questions
    for pat, want in YES_NO_QUESTION_PATTERNS:
        if re.search(pat, q):
            for l in labels:
                if l.strip().lower() in YES_NO[want]:
                    return l
            return None

    # 2) language proficiency, whichever scale this employer used
    lang = next((n for n, p in LEVEL_SELECT_PATTERNS.items()
                 if re.search(p, q)), None)
    if lang:
        target = LEVEL_TARGET[lang]
        scored = [(l, _level_score(l)) for l in labels]
        exact = [l for l, s in scored if s == target]
        if exact:
            # prefer the shortest/most exact label (e.g. "A1" over "A1 - Anfänger*in")
            return min(exact, key=len)
        above = [s for _, s in scored if s is not None and s > target]
        if above and lang == "english":
            top = max(above)
            return next((l for l, s in scored if s == top), None)
        weaker = [s for _, s in scored if s is not None and s < target]
        if weaker:
            return next((l for l, s in scored if s == max(weaker)), None)
    return None


DATE_QUESTION_PATTERNS = [
    (r"beenden|abschlie|graduate|graduation|finish.{0,20}(stud|degree)|"
     r"end.{0,12}(stud|degree|ausbildung)|studiendatum|voraussichtlich",
     "screening_answers.study_end"),
    (r"geburts|born|birth|geburtstag|date of birth|dob", "identity.date_of_birth"),
    (r"immatrikul|studienbeginn|studium (begonnen|seit)|since|seit|"
     r"start of (studies|education)|educations?.*start",
     "screening_answers.study_start"),
]


def _as_month_year(value: str) -> str | None:
    """Parse 07/2028 or 7.2028 -> '2028-07' (or reuse full-date parsing)."""
    m = re.match(r"\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\s*$", str(value or ""))
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}"
    return None
DATE_INPUT_HINT = re.compile(r"datum|date|tt\.?mm|dd\.?mm|mm\.?dd|jjjj|yyyy|"
                             r"jj/mm|yyyy-mm-dd|geburt|born", re.I)


def _as_iso(value: str) -> str | None:
    """Accept 12.06.1999 / 1999-06-12 / 06/12/1999 / 2028-07 -> ISO YYYY-MM-DD."""
    import re as _re
    v = str(value or "").strip()
    m = _re.match(r"^\s*(\d{4})-(\d{1,2})\s*$", v)          # 'YYYY-MM'
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-01"
    m = _re.match(r"^\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\s*$", v)  # 'MM/YYYY'
    if m:
        return f"{m.group(2)}-{int(m.group(1)):02d}-01"
    m = _re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", v)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = _re.search(r"(\d{1,2})[./](\d{1,2})[./](\d{4})", v)
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return None


MONTH_YEAR_HINT = re.compile(r"mm\s*[/.\-]\s*(jjjj|yyyy)|monat.*jahr|"
                             r"month.*year|tt\s*[.]\s*jjjj", re.I)


def _date_display(iso: str, hint: str) -> str:
    """Render an ISO date the way this field expects it."""
    y, m, d = iso.split("-")
    h = (hint or "").lower()
    delim = "/" if "/" in h else "." if "." in h else "-"
    if re.search(r"y{2,4}\s*[-/.]\s*m{1,2}\s*[-/.]\s*d{1,2}|jjjj\s*[-/.]\s*tt", h):
        return f"{y}-{m}-{d}"          # ISO first — "yyyy-mm-dd" also matches mm-dd
    dd_first = re.search(r"dd\s*([./-])\s*mm|tt\s*([./-])\s*mm|tag\s*[./-]\s*monat", h)
    mm_first = re.search(r"mm\s*([./-])\s*dd|monat\s*[./-]\s*tag", h)
    if dd_first:
        sep = (dd_first.group(1) or dd_first.group(2)) if dd_first.lastindex else delim
        return f"{d}{sep}{m}{sep}{y}"
    if mm_first:
        return f"{m}{delim}{d}{delim}{y}"
    return f"{d}.{m}.{y}"


START_DATE_PATTERN = re.compile(
    r"frühestmöglich|frühst|fruehst|earliest|soonest|start ?datum|start date|"
    r"ab wann|wann.*(beginn|start)|available from|^(early|earliest).*start",
    re.I)


def _resolve_start_date(profile: dict) -> str | None:
    """Earliest start date. 'Immediately' means the 1st of the next month."""
    from datetime import date as _date
    raw = str(profile.get("screening_answers", {}).get("earliest_start", "")).strip()

    def first_of_next_month() -> str:
        t = _date.today()
        y, m = (t.year + 1, 1) if t.month == 12 else (t.year, t.month + 1)
        return _date(y, m, 1).isoformat()

    if re.search(r"immediate|sofort|now|directly|as soon", raw, re.I):
        return first_of_next_month()
    iso = _as_iso(raw)
    return iso


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")


def fill_date(el, value: str) -> tuple[bool, str]:
    """Put a date into LinkedIn's date widget. Returns (ok, attempted).

    LinkedIn uses at least three shapes: plain text (dd.mm.yyyy), native
    type=date (ISO), and data-testid="date-picker-input", which only accepts a
    typed keystroke sequence. Success = the input holds a date and is no
    longer flagged aria-invalid — we don't assume the rendered format.
    """
    iso = _as_iso(value) or value
    expected = _digits(value if _digits(value) else iso)

    def accepted() -> bool:
        try:
            invalid = el.evaluate("e => e.getAttribute('aria-invalid')")
            cur = _digits(el.input_value())
            return invalid != "true" and bool(cur) and (cur == expected or len(cur) == 8)
        except Exception:
            return False

    def attempt(v: str, via: str) -> bool:
        try:
            el.evaluate("e => { e.focus(); }")
            if via == "fill":
                try:
                    el.fill(v, timeout=2500)
                except Exception:
                    pass
            elif via == "setter":
                el.evaluate("""(e, val) => {
                    const s = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value').set;
                    s.call(e, val);
                    e.dispatchEvent(new Event('input', { bubbles: true }));
                    e.dispatchEvent(new Event('change', { bubbles: true }));
                }""", v)
            else:  # typed keystrokes
                for ch in v:
                    el.press(ch if ch.isalnum() else ("Minus" if ch == "-" else ch))
                    human_pause(0.02, 0.05)
            el.evaluate("""e => { e.dispatchEvent(new Event('input',{bubbles:true}));
                                    e.dispatchEvent(new Event('change',{bubbles:true})); }""")
            el.evaluate("e => e.blur()")
            human_pause(0.2, 0.4)
            return accepted()
        except Exception as e:
            log.debug("date attempt %s via %s failed: %s", v, via, e)
            return False

    for candidate, how in ((value, "fill"), (value, "type"), (iso, "setter"),
                           (iso, "type")):
        if attempt(candidate, how):
            return True, candidate
    return False, value


def answer_date_field(profile: dict, label: str, hint: str = "") -> str | None:
    """Return a date string for date/date-picker fields, or None if unknown."""
    lbl = clean_text(label).lower()
    if START_DATE_PATTERN.search(clean_text(label)):
        iso = _resolve_start_date(profile)
        return _date_display(iso, hint) if iso else None
    for pat, path in DATE_QUESTION_PATTERNS:
        if re.search(pat, lbl):
            try:
                raw = resolve_profile_value(profile, path)
            except Exception:
                return None
            my = _as_month_year(raw)
            if my and (MONTH_YEAR_HINT.search(hint) or MONTH_YEAR_HINT.search(lbl)):
                # month/year widget: feed the value in the locale it expects
                y, m = my.split("-")
                sep = "." if re.search(r"tt\s*[.]\s*jjjj|monat", (hint + lbl), re.I) else "/"
                return f"{m}{sep}{y}"
            iso = _as_iso(raw)
            if not iso:
                return None
            return _date_display(iso, hint)
    return None


def type_text(el, value: str) -> bool:
    """Type into a stubborn React/masked input and verify it took the value."""
    try:
        el.click()
        try:
            el.evaluate("""e => { e.value = ''; e.dispatchEvent(
                new Event('input', { bubbles: true })); }""")
        except Exception:
            pass
        el.press_sequentially(value, delay=40)
        el.dispatch_event("input")
        el.dispatch_event("change")
        human_pause(0.2, 0.4)
        el.evaluate("e => e.blur()")
    except Exception as e:
        log.debug("type_text failed: %s", e)
        return False
    try:
        return el.input_value().strip() == value.strip()
    except Exception:
        return True


NUMERIC_HINT = re.compile(
    r"\b(eur|€|euro|brutto|netto|zahl|number|anzahl|wie\s+viele|"
    r"prozent|percent|stunden?|hours?|jahre|years|monat|monate|month|months)\b", re.I)


def coerce_number(value: str, label: str) -> str | None:
    """Reduce a profile answer to a bare number for a numeric field."""
    if value == "__COUNTRY__":
        return value
    # a range like 13–20: for an expectation, take the upper bound
    m = re.search(r"(\d[\d.,]*)\s*(?:[–—-]|bis|to)\s*(\d[\d.,]*)", value, re.I)
    if m:
        return m.group(2).replace(".", "").replace(",", ".")
    m = re.search(r"\d[\d.,]*", value)
    return m.group(0) if m else None


def screenshot(page: Page, name: str) -> Path:
    path = LOGS / f"{datetime.now():%Y%m%d_%H%M%S}_{name}.png"
    try:
        page.screenshot(path=str(path))
    except Exception:
        pass
    return path


# ------------------------------------------------------------- LinkedIn
class LinkedInEasyApply:
    def __init__(self, page: Page, profile: dict, resume_pdf: Path,
                 cover_pdf: Path | None, cover_text: str | None,
                 auto_submit: bool, keep_open_on_abort: bool = False):
        self.page = page
        self.keep_open_on_abort = keep_open_on_abort
        self.profile = profile
        self.resume_pdf = resume_pdf
        self.cover_pdf = cover_pdf
        self.cover_text = cover_text
        self.auto_submit = auto_submit
        self.unknown_questions: list[str] = []

    def repair_invalid_fields(self) -> None:
        """Fix controls LinkedIn itself flagged invalid.

        Some required inputs (e.g. the start-date box on the review page) are
        rendered outside the main <dialog>, so the modal-scoped passes miss them
        and the form refuses to advance. This pass is page-wide on purpose.
        """
        bad = self.page.locator(
            "input[aria-invalid='true'], select[aria-invalid='true'], "
            "textarea[aria-invalid='true'], .artdeco-text-input--error")
        for i in range(bad.count()):
            el = bad.nth(i)
            try:
                if not el.is_visible():
                    continue
                tag = el.evaluate("e => e.tagName")
                label = clean_text(el.evaluate(LABEL_JS))
                if tag == "SELECT":
                    value = answer_level_select(
                        self.profile, label,
                        el.evaluate("e => [...e.options].map(o => [o.value, o.text])"))
                    if value:
                        ok = select_option_safe(el, label=value)
                        log.info("repaired select %-40s -> %s (ok=%s)", label[:40], value, ok)
                    continue
                if el.input_value().strip():
                    # a wrong value (e.g. letters in a numeric box) is NOT a
                    # missing one — but it still blocks Next, so re-coerce it
                    try:
                        valid = el.evaluate("e => e.checkValidity ? e.checkValidity() : true")
                    except Exception:
                        valid = True
                    if valid:
                        continue
                    label2 = clean_text(el.evaluate(LABEL_JS))
                    coerced = coerce_number(el.input_value(), label2)
                    if coerced and coerced != el.input_value().strip():
                        if type_text(el, coerced):
                            log.info("re-coerced invalid %-35s -> %s",
                                     label2[:35], coerced)
                            continue
                    self.unknown_questions.append(
                        f"field {label2[:50]!r} holds invalid '{el.input_value()[:30]}'")
                    continue
                hint = " ".join(filter(None, [
                    el.evaluate("e => e.placeholder || ''"),
                    el.evaluate("e => e.getAttribute('aria-label') || ''"),
                    el.evaluate("e => e.getAttribute('data-testid') || ''"), label]))
                value = None
                if DATE_INPUT_HINT.search(hint) or "date-picker" in hint or START_DATE_PATTERN.search(label):
                    value = answer_date_field(self.profile, label, hint)
                    if value:
                        ok, attempted = fill_date(el, value)
                        log.info("repaired date %-40s -> %s (ok=%s)",
                                 label[:40], attempted, ok)
                        if not ok:
                            self.unknown_questions.append(
                                f"date field {label[:50]!r} rejected '{value}'")
                    else:
                        self.unknown_questions.append(
                            f"date field {label[:50]!r} — no known date")
                    continue
                ftype = el.evaluate("e => e.type || ''")
                value = self.answer_for(
                    label or el.evaluate("e => e.getAttribute('aria-label') || ''"),
                    is_textarea=(tag == "TEXTAREA"))
                if value == "__COUNTRY__":
                    continue
                if value:
                    if ftype == "number" or NUMERIC_HINT.search(label):
                        value = coerce_number(value, label) or value
                    ok = type_text(el, value)
                    log.info("repaired %-40s -> %s (ok=%s)", label[:40], str(value)[:40], ok)
            except Exception as e:
                log.debug("repair error: %s", e)

    def dump_stuck_state(self, modal) -> None:
        """Page-wide forensic dump when the form refuses to advance."""
        try:
            info = self.page.evaluate("""() => {
                const clean = s => (s || '').replace(/\\s+/g, ' ').trim();
                const dl = document.querySelector('dialog');
                const scope = dl || document.body;
                const ctrls = [...scope.querySelectorAll('input:not([type=hidden]),select,textarea')]
                    .filter(e => e.offsetParent)
                    .map(e => {
                        let lab = '';
                        if (e.id) lab = clean(scope.querySelector(`label[for="${e.id}"]`)?.innerText)
                                   || clean(document.querySelector(`label[for="${e.id}"]`)?.innerText);
                        if (!lab && e.labels?.length) lab = clean(e.labels[0].innerText);
                        return { tag: e.tagName, type: e.type || '', id: e.id,
                            req: !!e.required || e.getAttribute('aria-required') === 'true',
                            invalid: e.getAttribute('aria-invalid'),
                            checked: !!e.checked, val: (e.value || '').slice(0, 30),
                            label: lab.slice(0, 90),
                            vis: (e.closest('fieldset') ? 'fs' : '')
                                + (e.closest('[role=radiogroup]') ? 'rg' : '') };
                    });
                const btns = [...scope.querySelectorAll('button')].filter(b => b.offsetParent)
                    .map(b => ({ t: clean(b.innerText).slice(0, 30), dis: !!b.disabled }));
                const errs = [...scope.querySelectorAll('*')].filter(e => {
                        if (!e.offsetParent || e.children.length > 2) return false;
                        const t = clean(e.innerText);
                        return t && t.length < 120 && /required|erforderlich|ungültig|invalid|bitte|please|choose|w[aä]hle/i.test(t);
                    }).map(e => clean(e.innerText)).filter((v, i, a) => a.indexOf(v) === i);
                const pages = clean(scope.innerText.match(/\\d+\\/\\d+ pages?/)?.[0] || '');
                return { ctrls, btns, errs: errs.slice(0, 10), pages };
            }""")
            log.warning("STUCK STATE — page marker: %s", info.get("pages", "?"))
            for e in info.get("errs", []):
                log.warning("  on-screen message: %s", e)
            for c in info.get("ctrls", []):
                log.info("  ctrl %s/%s id=%s req=%s invalid=%s checked=%s val=%r label=%r",
                         c["tag"], c["type"], c["id"], c["req"], c["invalid"],
                         c["checked"], c["val"], c["label"][:70])
            for b in info.get("btns", []):
                if b["t"]:
                    log.info("  button %r disabled=%s", b["t"], b["dis"])
        except Exception as ex:
            log.debug("dump failed: %s", ex)

    def collect_validation_errors(self, modal) -> list[str]:
        """Read LinkedIn's inline validation messages so a stuck form explains itself."""
        try:
            raw = modal.evaluate("""m => {
                const clean = s => (s||'').replace(/\\s+/g,' ').trim();
                const out = [];
                const sels = ['.artdeco-inline-message--error',
                              '[data-test-form-element] [class*="error"]',
                              '[aria-invalid="true"]',
                              '.artdeco-text-input--error',
                              '[class*="inline-message--error"]'];
                for (const s of sels) {
                    m.querySelectorAll(s).forEach(e => {
                        if (!e.offsetParent) return;
                        const t = clean(e.innerText || e.getAttribute('aria-label')
                                        || e.getAttribute('placeholder'));
                        if (t && t.length < 200 && !out.includes(t)) out.push(t);
                    });
                }
                // an invalid control with no message still counts: name the field
                m.querySelectorAll('[aria-invalid="true"], input:invalid, select:invalid')
                 .forEach(e => {
                    if (!e.offsetParent) return;
                    let lab = '';
                    if (e.id) {
                        const l = m.querySelector(`label[for="${e.id}"]`);
                        if (l) lab = clean(l.innerText);
                    }
                    const msg = 'invalid field without message: ' + (lab || e.name || e.type);
                    if (!out.includes(msg)) out.push(msg);
                 });
                return out;
            }""")
            return [clean_text(x) for x in raw if clean_text(x)]
        except Exception:
            return []

    def fill_text_fields(self, modal) -> bool:
        """Fill visible text inputs/textareas. Returns False on unknown REQUIRED field."""
        inputs = modal.locator("input[type='text'], input[type='tel'], input[type='email'], textarea")
        for i in range(inputs.count()):
            el = inputs.nth(i)
            try:
                if not el.is_visible() or el.input_value().strip():
                    continue
                label = ""
                try:
                    label = el.evaluate(LABEL_JS)
                except Exception:
                    pass
                ftype = el.evaluate("el => el.type || ''")
                hint = " ".join(filter(None, [
                    el.evaluate("el => el.placeholder || ''"),
                    el.evaluate("el => el.getAttribute('aria-label') || ''"),
                    el.evaluate("el => el.getAttribute('data-testid') || ''"),
                    label if DATE_INPUT_HINT.search(clean_text(label)) else "",
                ]))
                if ftype == "date" or "date-picker" in hint or DATE_INPUT_HINT.search(hint):
                    # date input / date picker — LinkedIn's masked widget
                    if ftype == "date":
                        value = answer_date_field(self.profile, label, "yyyy-mm-dd")
                    else:
                        value = answer_date_field(self.profile, label, hint)
                    if value:
                        ok, attempted = fill_date(el, value)
                        log.info("date %-40s -> %s (ok=%s)",
                                 clean_text(label)[:40], attempted, ok)
                        if not ok and el.evaluate(
                                "e => e.required || e.getAttribute('aria-required') === 'true'"):
                            self.unknown_questions.append(
                                f"date field {clean_text(label)[:50]!r} rejected '{value}'")
                            return False
                    else:
                        # NEVER let free text (e.g. "Immediately") go into a
                        # date widget — that silently breaks validation
                        if el.evaluate(
                                "e => e.required || e.getAttribute('aria-required') === 'true'"):
                            self.unknown_questions.append(
                                f"date field {clean_text(label)[:50]!r} — no known date")
                        human_pause(0.2, 0.5)
                    continue
                value = self.answer_for(label, is_textarea=el.evaluate("el => el.tagName") == "TEXTAREA")
                if value is None and el.evaluate("el => el.type") == "tel":
                    # LinkedIn's phone input carries no label; identify it by type
                    value = phone_parts(self.profile)[1]
                if value is None:
                    required = el.evaluate("el => el.required || el.getAttribute('aria-required') === 'true'")
                    if required:
                        self.unknown_questions.append(label or "(unlabeled field)")
                        return False
                    continue
                if value == "__COUNTRY__":
                    ok = set_country_combobox(el, phone_parts(self.profile)[0])
                    log.info("country combobox -> %s (ok=%s)", label[:40], ok)
                    continue
                numeric = ftype in ("number",) or el.evaluate(
                    "e => ['numeric','decimal'].includes(e.inputmode || '')")
                numeric = numeric or bool(NUMERIC_HINT.search(clean_text(label)))
                if numeric and ftype != "tel":
                    coerced = coerce_number(value, label)
                    if coerced is None:
                        if el.evaluate("e => e.required || e.getAttribute('aria-required') === 'true'"):
                            self.unknown_questions.append(
                                f"numeric field {clean_text(label)[:50]!r} — no number for '{value}'")
                            return False
                        continue
                    log.info("numeric %-40s -> %s", clean_text(label)[:40], coerced)
                    value = coerced
                ok = False
                try:
                    el.click()
                    el.fill(value)
                    ok = el.input_value().strip() == value.strip()
                except Exception:
                    ok = type_text(el, value)
                if not ok:
                    # React widgets ignore fill() — fall back to real keystrokes
                    ok = type_text(el, value)
                log.info("filled %-25s = %-30s (ok=%s)", label[:25], value[:30], ok)
                if not ok and el.evaluate("e => e.required || e.getAttribute('aria-required') === 'true'"):
                    self.unknown_questions.append(f"field {clean_text(label)[:50]!r} rejected input")
                    return False
                # LinkedIn text boxes silently reject malformed content
                # (e.g. letters inside a numeric salary field) and the Next
                # click then does nothing. Verify the DOM constraint and
                # re-coerce if it failed.
                try:
                    valid = el.evaluate("e => e.checkValidity ? e.checkValidity() : true")
                except Exception:
                    valid = True
                if not valid and value != "__COUNTRY__":
                    coerced = coerce_number(value, label)
                    if coerced and coerced != value:
                        log.info("invalid input re-coerced %-20s -> %s",
                                 clean_text(label)[:20], coerced)
                        ok2 = type_text(el, coerced)
                        valid = el.evaluate("e => e.checkValidity ? e.checkValidity() : true")
                        if valid and ok2:
                            value = coerced
                if not valid and el.evaluate(
                        "e => e.required || e.getAttribute('aria-required') === 'true'"):
                    self.unknown_questions.append(
                        f"field {clean_text(label)[:50]!r} did not accept '{value}'")
                    return False
                human_pause(0.3, 0.9)
            except Exception as e:
                log.debug("field fill error: %s", e)
        return True

    def answer_for(self, label: str, is_textarea: bool = False) -> str | None:
        lbl = clean_text(label).lower()
        if is_textarea and ("cover" in lbl or "anschreiben" in lbl) and self.cover_text:
            return self.cover_text[:4000]
        for pat, key in LABEL_ANSWERS:
            if re.search(pat, lbl):
                if key == "phone_country":
                    return "__COUNTRY__"
                if key == "phone":
                    return phone_parts(self.profile)[1]
                return resolve_profile_value(self.profile, key)
        for pat, key in SCREENING_PATTERNS:
            if re.search(pat, lbl):
                return resolve_profile_value(self.profile, key)
        return None

    def handle_selects_and_radios(self, modal) -> bool:
        selects = modal.locator("select")
        for i in range(selects.count()):
            el = selects.nth(i)
            try:
                if not el.is_visible():
                    continue
                opts = [o.strip() for o in el.locator("option").all_inner_texts()]
                if not opts:
                    continue
                # country-code dropdown: options look like "Germany (+49)"
                if sum(1 for o in opts if re.search(r"\(\+\d+\)", o)) >= 5:
                    target = pick_country_option(self.profile, opts)
                    if target:
                        ok = select_option_safe(el, label=target)
                        log.info("country code -> %s (ok=%s)", target, ok)
                    human_pause(0.3, 0.8)
                    continue
                # email dropdown: options are addresses
                if any("@" in o for o in opts):
                    target = next((o for o in opts if o.strip().lower()
                                   == self.profile["identity"]["email"].lower()), None)
                    if target:
                        ok = select_option_safe(el, label=target)
                        log.info("email select -> %s (ok=%s)", target, ok)
                    continue
                label = clean_text(el.evaluate(LABEL_JS))
                if re.search(r"select language|language| Sprache|sprache", label, re.I):
                    continue  # LinkedIn footer locale switch — never touch it
                if el.evaluate("e => e.required || e.getAttribute('aria-required') === 'true'"):
                    value = answer_level_select(
                        self.profile, label,
                        el.evaluate("e => [...e.options].map(o => [o.value, o.text])"))
                    if value is not None:
                        ok = select_option_safe(el, label=value)
                        log.info("answered %-45s -> %s (ok=%s)",
                                 clean_text(label)[:45], value, ok)
                        human_pause(0.3, 0.8)
                    else:
                        # Never guess: leave it, and let the run abort as needs_manual
                        # rather than submitting a wrong answer.
                        log.info("REQUIRED select unanswered: %-45s opts=%s",
                                 clean_text(label)[:45], opts[:4])
                        self.unknown_questions.append(clean_text(label) or "(unlabeled dropdown)")
                else:
                    log.info("optional select left untouched: %s", clean_text(label)[:40])
            except Exception as e:
                log.debug("select error: %s", e)

        # Radio groups, found by their shared `name` attribute (LinkedIn mixes
        # fieldset, role=radiogroup and plain div wrappers between postings).
        try:
            groups = self.page.evaluate(RADIO_GROUPS_JS)
        except Exception:
            groups = []
        for grp in groups:
            if grp.get("checked"):
                continue
            try:
                legend = clean_text(grp.get("question", ""))
                legend_l = legend.lower()
                labels = [clean_text(
                    self.page.locator(f"input[type=radio][id='{rid}']").first
                    .evaluate(OPTION_JS)).lower() for rid in grp["ids"]]
                joined = " | ".join(labels)

                choice = None
                if re.search(r"consent|privacy|datenschutz|agree|zustimm|"
                             r"terms|bedingungen|confirm|bestätig|ernsthaft|"
                             r"declare|erklärung|acknowledg|agb", legend_l):
                    choice = next((j for j, l in enumerate(labels)
                                   if l in ("yes", "ja", "y", "true")), None)
                if choice is None and re.search(
                        r"authorized|berechtigt|eligible|legally|recht|work permit|"
                        r"arbeitserlaubnis|study|enrolled|immatrikul|student|"
                        r"wohnhaft|based in|standort", legend_l):
                    choice = next((j for j, l in enumerate(labels)
                                   if l in ("yes", "ja", "y")), None)
                if choice is None and re.search(r"sponsor|visa", legend_l):
                    choice = next((j for j, l in enumerate(labels)
                                   if l in ("no", "nein", "n")), None)

                if choice is not None:
                    chosen_id = grp["ids"][choice]
                    try:
                        if grp.get("name"):
                            loc = self.page.locator(
                                f"input[type=radio][name='{grp['name']}']")
                            (loc.nth(choice) if loc.count() > choice else loc.first) \
                                .check(timeout=4000)
                        else:
                            self.page.locator(f"#{chosen_id}").check(timeout=4000)
                    except Exception:
                        self.page.locator(f"#{chosen_id}") \
                            .evaluate("e => { e.click(); e.dispatchEvent("
                                      "new Event('change', {bubbles:true})); }")
                    log.info("radio %-45s -> %s", legend[:45], labels[choice])
                    human_pause(0.3, 0.8)
                elif grp.get("required"):
                    if not labels or not any(labels):
                        log.info("required radio group unreadable: %s", legend[:60])
                    else:
                        log.info("required radio group I won't guess: %s :: %s",
                                 legend[:60], joined[:60])
                    self.unknown_questions.append(
                        f"radio {legend[:60]!r} :: {joined[:40]}")
            except Exception as e:
                log.debug("radio error: %s", e)

        # Required checkboxes (consent / privacy) that are left unticked
        for i in range(modal.locator("input[type='checkbox']").count()):
            cb = modal.locator("input[type='checkbox']").nth(i)
            try:
                if not cb.is_visible() or cb.is_checked():
                    continue
                lab = clean_text(cb.evaluate(LABEL_JS)).lower()
                if re.search(r"consent|privacy|datenschutz|agree|zustimm|"
                             r"terms|bedingungen|confirm|bestätig|agb", lab):
                    cb.check()
                    log.info("checked consent box: %s", lab[:50])
                    human_pause(0.2, 0.6)
            except Exception as e:
                log.debug("checkbox error: %s", e)

        return not self.unknown_questions

    def _upload_context(self, btn) -> str:
        """Text of the section an Upload button belongs to (LinkedIn no longer
        exposes data-test-form-element, so we walk up to a single-button parent)."""
        try:
            return clean_text(btn.evaluate("""btn => {
                const clean = s => (s||'').replace(/\\s+/g,' ').trim();
                let n = btn;
                for (let i = 0; i < 8 && n; i++, n = n.parentElement) {
                    const t = clean(n.innerText);
                    if (!t || t.length > 300) continue;
                    const ups = [...n.querySelectorAll('button')]
                        .filter(b => /^(upload|hochladen)$/i.test(clean(b.innerText)));
                    if (ups.length > 1) return '';
                    if (/cover|anschreiben|motivation|lebenslauf|resume|\\bcv\\b|vitae/i.test(t))
                        return t;
                }
                return '';
            }"""))
        except Exception:
            return ""

    def handle_uploads(self, modal) -> None:
        """Upload CV/cover letter when a step actually demands it.

        LinkedIn auto-attaches the profile resume on Easy Apply, so we never
        click that Upload button (clicking it on the review page also opens a
        native chooser that stalls the run). Cover letter is clicked at most
        once, with a short chooser timeout.
        """
        if not hasattr(self, "_cover_done"):
            self._cover_done = False
        buttons = modal.locator("button:visible").filter(
            has_text=re.compile(r"^\s*(Upload|Hochladen)\s*$", re.I))
        for i in range(buttons.count()):
            btn = buttons.nth(i)
            try:
                ctx = self._upload_context(btn)
                if not ctx:
                    continue
                is_cover = bool(re.search(r"cover|anschreiben|motivation", ctx, re.I))
                kind = "cover letter" if is_cover else "resume"
                if re.search(r"[\wäöüß.\-]+\.(pdf|docx?|odt)", ctx, re.I):
                    log.info("%s already has a file attached — leaving it", kind)
                    continue
                if not is_cover:
                    log.info("resume section open — leaving LinkedIn's profile copy in place")
                    continue
                if self._cover_done:
                    continue
                if not (self.cover_pdf and Path(self.cover_pdf).exists()):
                    msg = ("cover letter required — no PDF generated for this job yet "
                           "(write it, then rerun)")
                    log.warning("%s", msg)
                    self.unknown_questions.append(msg)
                    continue
                path = Path(self.cover_pdf)
                try:
                    with self.page.expect_file_chooser(timeout=3500) as info:
                        btn.click()
                    info.value.set_files(str(path))
                except Exception:
                    human_pause(0.4, 0.8)
                    fi = self.page.locator("input[type='file']")
                    if not fi.count():
                        log.warning("upload click produced no file chooser/input")
                        continue
                    fi.last.set_input_files(str(path))
                self._cover_done = True
                log.info("uploaded %s: %s", kind, path.name)
                human_pause(0.8, 1.5)
            except Exception as e:
                log.debug("upload error: %s", e)

    CLOSED_PATTERNS = (
        r"no longer accepting applications",
        r"no longer accepting",
        r"this job is no longer available",
        r"job (is )?(closed|expired)",
        r"position (is )?(closed|has been filled|no longer available)",
        r"applications? (are|is) closed",
        r"stellenanzeige (ist )?(nicht mehr|geschlossen)",
        r"bewerbungen? (sind|ist) (nicht mehr|geschlossen)",
        r"keine neuen bewerbungen",
        r"diese stelle ist nicht mehr",
        r"position is no longer",
    )

    def posting_is_closed(self) -> bool:
        """LinkedIn keeps the page live but drops the apply button when closed."""
        page = self.page
        try:
            body = clean_text(page.evaluate(
                "() => (document.body.innerText || '').slice(0, 2500)"))
        except Exception:
            return False
        for pat in self.CLOSED_PATTERNS:
            if re.search(pat, body, re.I):
                return True
        # Only trust "no apply button" when we really are on a job detail page;
        # a slow render or an auth wall must not be mistaken for a closed post.
        looks_like_job = page.evaluate("""() => {
            const t = (document.body.innerText || '').toLowerCase();
            if (/sign in|anmelden|join (now|linkedin)|create an account/.test(t.slice(0, 400)))
                return false;
            return !!(document.querySelector('.jobs-easy-apply, .topcard__title, h1')
                   || /apply|bewerbung|apply now/.test(t));
        }""")
        if not looks_like_job:
            return False
        if pick_text(page, EASY_APPLY_WORDS) is None:
            has_apply = page.evaluate(
                """() => [...document.querySelectorAll('a,button')].some(b => {
                    const t = ((b.innerText || '') + ' ' +
                               (b.getAttribute('aria-label') || '')).toLowerCase();
                    return b.offsetParent && /apply|bewerb|jetzt bewerben|schnellbewerbung/
                        .test(t) && !/already applied|beworben/.test(t);
                })""")
            if not has_apply:
                log.info("no apply control on a loaded job page — treating as closed")
                return True
        return False

    def _apply_dialog_open(self) -> bool:
        """True once LinkedIn's Easy Apply modal is on screen."""
        for _ in range(14):
            if self.page.locator("dialog[data-testid='dialog'], dialog[open]").count():
                return True
            self.page.wait_for_timeout(500)
        return False

    def run(self, job_url: str) -> str:
        """Returns: applied / needs_manual / failed / already_applied / not_easy_apply / closed"""
        page = self.page
        try:
            page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            log.warning("first load failed (%s) — retrying once", str(e)[:50])
            try:
                page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e2:
                log.error("job page would not load: %s", str(e2)[:60])
                return "failed"
        human_pause(2, 4)

        # LinkedIn's footer language dropdown can flip the whole UI to another
        # language (we accidentally did this once); detect and revert.
        if ui_locale_looks_wrong(page):
            log.warning("LinkedIn UI is not in English — resetting language")
            if force_ui_locale(page):
                page.reload(wait_until="domcontentloaded", timeout=45000)
                human_pause(2, 3)
            else:
                log.error("could not reset LinkedIn UI language — aborting safely")
                return "failed"

        # dismiss cookie consent if present
        try:
            accept = page.locator("button:has-text('Accept')").first
            if accept.count() and accept.is_visible():
                accept.click()
                human_pause(1, 2)
        except Exception:
            pass

        # Closed/expired posting — skip it and move on to the next job.
        if self.posting_is_closed():
            log.info("posting closed or no longer accepting applications")
            return "closed"

        if page.locator("text=/already applied|beworben/i").count():
            return "already_applied"

        btn = pick_text(page, EASY_APPLY_WORDS)
        if btn is None:
            return "not_easy_apply"
        btn.click()
        human_pause(1.5, 3)

        if not self._apply_dialog_open():
            # An interrupted earlier run leaves a LinkedIn draft behind, and then
            # Easy Apply no longer opens the dialog. Resume that draft instead
            # of operating on the job feed.
            cont = pick_text(page, ("Continue application", "Continue your application",
                                    "Draft", "Wiederaufnehmen", "Fortsetzen",
                                    "Anwendung fortsetzen"))
            if cont is not None:
                log.info("resuming saved draft via %r", clean_text(cont.inner_text())[:40])
                cont.click()
                human_pause(1.5, 3)
            if not self._apply_dialog_open():
                log.warning("Easy Apply dialog did not open — stopping instead of "
                            "clicking around the job feed")
                if not self.keep_open_on_abort:
                    pass
                return "needs_manual"

        last_signature = None
        stuck = 0
        for _step in range(12):
            # Scope every action to the Easy Apply modal. Falling back to the
            # page body makes the engine click job-feed arrows forever, which
            # looks like a hang and applies to nothing.
            modal = page.locator("dialog[data-testid='dialog'], dialog[open]").last
            if not modal.count():
                log.warning("apply dialog disappeared mid-flow — aborting")
                return "needs_manual"
            vis_inputs = modal.locator("input:visible, textarea:visible")
            log.info("step %d: %d visible inputs", _step, vis_inputs.count())

            # Step signature = "3/4 pages" + the questions on screen. If a click
            # does not change it, LinkedIn refused to advance (validation).
            signature = clean_text(modal.inner_text()[:220])
            if signature == last_signature:
                stuck += 1
                if stuck >= 2:
                    errs = self.collect_validation_errors(modal)
                    self.dump_stuck_state(modal)
                    if errs:
                        log.warning("form is stuck; LinkedIn says: %s", "; ".join(errs))
                        self.unknown_questions.extend(errs)
                    else:
                        log.warning("form did not advance twice on the same step and "
                                    "showed no validation message — aborting")
                    if not self.keep_open_on_abort:
                        self._close_modal()
                    return "needs_manual"
            else:
                stuck = 0
            last_signature = signature

            if not self.fill_text_fields(modal):
                log.warning("unknown required question(s): %s — aborting cleanly", self.unknown_questions)
                if not self.keep_open_on_abort:
                    self._close_modal()
                return "needs_manual"
            if not self.handle_selects_and_radios(modal):
                log.warning("required dropdown(s) I will not guess: %s — aborting cleanly",
                            self.unknown_questions)
                if not self.keep_open_on_abort:
                    self._close_modal()
                return "needs_manual"
            self.handle_uploads(modal)
            self.repair_invalid_fields()
            if self.unknown_questions:
                log.warning("unresolved requirement(s): %s — aborting cleanly",
                            self.unknown_questions)
                if not self.keep_open_on_abort:
                    self._close_modal()
                return "needs_manual"
            human_pause(1, 2)

            submit_btn = pick_text(page, SUBMIT_WORDS)
            review_btn = pick_text(page, REVIEW_WORDS)
            next_btn = pick_text(page, NEXT_WORDS)

            if submit_btn is not None:
                screenshot(page, "before_submit")
                if not self.auto_submit:
                    return "ready_to_submit"
                submit_btn.click()
                human_pause(2, 4)
                screenshot(page, "after_submit")
                return "applied"
            if review_btn is not None:
                log.info("clicking %s", clean_text(review_btn.inner_text()))
                review_btn.click()
            elif next_btn is not None:
                log.info("clicking %s", clean_text(next_btn.inner_text()))
                next_btn.click()
            else:
                log.warning("no navigation button found on step %d", _step)
                self._close_modal()
                return "needs_manual"
            human_pause(1.5, 3)
        self._close_modal()
        return "failed"

    def _close_modal(self):
        try:
            self.page.keyboard.press("Escape")
            human_pause(0.5, 1)
            discard = self.page.locator("button:has-text('Discard'), button:has-text('Verwerfen')").first
            if discard.count():
                discard.click()
        except Exception:
            pass


# --------------------------------------------------------------- accounts
def register_account(platform: str, email: str, keychain_item: str, notes: str = "") -> None:
    ACCOUNTS_REGISTRY.parent.mkdir(exist_ok=True)
    data = json.loads(ACCOUNTS_REGISTRY.read_text()) if ACCOUNTS_REGISTRY.exists() else []
    data.append({
        "platform": platform,
        "email": email,
        "keychain_item": keychain_item,
        "created": datetime.now().isoformat(timespec="seconds"),
        "notes": notes,
    })
    ACCOUNTS_REGISTRY.write_text(json.dumps(data, indent=2))


def apply_to_job(job: dict, resume_pdf: Path, cover_pdf: Path | None,
                 cover_text: str | None, auto_submit: bool,
                 headless: bool = False) -> str:
    """Dispatch by site. Returns status string."""
    profile = load_config("profile.yaml")
    pw, ctx = open_browser(headless=headless)
    try:
        page = ctx.new_page()
        site = job.get("site", "")
        url = job["job_url"]
        if site == "linkedin" or "linkedin.com" in url:
            engine = LinkedInEasyApply(page, profile, resume_pdf, cover_pdf, cover_text, auto_submit)
            result = engine.run(url)
        else:
            # External portal: open for manual handling
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            human_pause(2, 4)
            screenshot(page, "portal_opened")
            result = "portal_opened"
        log.info("%s @ %s -> %s", job.get("title"), job.get("company"), result)
        return result
    except Exception as e:
        log.error("apply failed for %s: %s", job.get("job_url"), e)
        return "failed"
    finally:
        ctx.close()
        pw.stop()

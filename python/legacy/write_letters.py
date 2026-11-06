"""Write cover letters for the current top Saxony shortlist entries.

Letters follow gerald-voice: direct, specific, honest about limits (German A1,
embedded is a pivot from web). Each is saved via save_letter() with the job id
registered, so apply_one/apply_queue pick it up automatically.

Usage: venv/bin/python scripts/write_letters.py
"""
from __future__ import annotations

import sys

from common import db, load_config
from cover_letter import save_letter

profile = load_config("profile.yaml")
ident = profile["identity"]

LETTERS: dict[str, tuple[str, str, str]] = {
    # job_id: (company, role, text)
    "76b45dd9c9671a11": (
        "NXP Semiconductors", "Praktikant System Engineering", """Sehr geehrte Damen und Herren,

KI auf kleiner Hardware zum Laufen zu bringen ist der Grund, warum ich Embedded Systems studiere. Die Aufgabe in Ihrem Team, Edge-AI-Modelle für Audio auf NXP-Hardware zu bringen, ist deshalb genau die Stelle, für die ich mich bewerbe.

Beruflich komme ich aus dem Web: vier Jahre Frontend bei Hubtel in Accra, davon ein Jahr die Migration des nationalen Kredit-Portals von Next.js auf Nuxt 4, außerdem der Citizen Web App für alle Bürger Ghanas mit Zahlungen, Standortlogik und Tests. Diese Jahre haben mir zwei Dinge gegeben: ich arbeite produktiv in TypeScript, Python und C, und ich kenne den Unterschied zwischen einer Demo und einem System, das im Betrieb bestehen muss.

Im Master an der TU Chemnitz arbeite ich an Verifikation digitaler Systeme, Hardware-Software-Codesign und Schaltungstests. Praktische Embedded-Erfahrung bring ich aus dem Studium und eigenen Projekten mit, nicht aus der Industrie. Ich fange also auf der Hardware-Seite neu an, mit Absicht und mit fünf Jahren Ingenieur-Disziplin dahinter.

Mein Deutsch ist noch auf A1-Niveau, ich lerne es täglich. Englisch ist meine Arbeitssprache, auch im Team-Kontext. Ein Praktikum in Dresden lässt sich mit dem Studium an der TU Chemnitz gut verbinden.

Über ein kurzes Gespräch freut sich
Gerald Bosu Ofori
"""),
    "4bd05222b6454298": (
        "Infineon Technologies", "Werkstudent Datenanalyse & KI", """Sehr geehrte Damen und Herren,

Datenanalysen sind dann wertvoll, wenn sie Entscheidungen auslösen, nicht nur Berichte füllen. Diese Haltung bringe ich aus vier Jahren Softwareentwicklung bei Hubtel in Accra mit, wo ich Messbarkeit immer dort eingebaut habe, wo sie fehlte.

Konkret: Bei der Migration des nationalen Kredit-Portals von Next.js auf Nuxt 4 habe ich Server-seitiges Rendering und eine Proxy-Schicht gebaut, die Credentials sicher hielt und Ladezeiten messbar verbesserte. In der Citizen Web App habe ich payment-flows mit Unit- und E2E-Tests abgesichert, mit React Testing Library und Vitest. TypeScript, JavaScript und Python sind meine Werkzeuge, AWS Certified Practitioner das Zertifikat, das den Cloud-Teil abdeckt.

Seit diesem Jahr studiere ich M.Sc. Embedded Systems an der TU Chemnitz. Daten und KI sind dabei kein Nebenfach für mich, sondern der Kern dessen, was ich langfristig tun will: Systeme, die in Echtzeit mit der echten Welt sprechen.

Zwei ehrliche Punkte: Mein Deutsch steht auf A1, Englisch ist fließend und die Arbeitssprache, in der ich alles geschrieben habe. Und meine Erfahrung liegt eher in Web-Stacks als in Ihrer Halbleiter-Domäne. Was ich mitbringe, ist Praxis in datengetriebener Software, Testkultur und die Geduld für saubere Analyse.

Ich freue mich auf den Austausch.
Gerald Bosu Ofori
"""),
    "434e8105490200e4": (
        "SachsenEnergie AG", "Praktikant Anwendungsmanagement & IT-Dokumentation", """Sehr geehrte Damen und Herren,

Dokumentation ist für mich die ehrlichste Disziplin der Softwareentwicklung. Wenn eine Anwendung nur so gut ist wie das Wissen über sie, dann entscheidet: Transparenz über Wartbarkeit. Genau dafür habe ich in meinem Berufsalltag immer wieder gekämpft, auch gegen den Termindruck.

Bei Hubtel in Accra, vier Jahre Frontend, war Dokumentieren Teil meiner Arbeit, nicht ein Anhängsel: für unsere React/Nodejs-Plattform Mettaxis habe ich technische Dokumentation geschrieben und direkt in der Anwendung verlinkt, damit Support und Entwicklung dieselbe Quelle lesen. Bei WeDID habe ich als Team-Lead für fünf Entwickler Code-Reviews, Anforderungsdokumente und Sprint-Reports verantwortet. Anwendungslandschaften durchschaubar machen, Systeminformationen pflegen, Prozesse aufschreiben: Das kenne ich von der practitioner-Seite.

Ich studiere M.Sc. Embedded Systems an der TU Chemnitz und suche ein Praktikum, bei dem Struktur und Systemverständnis zählen. Dresden ist von Chemnitz gut erreichbar.

Offen gesagt: Mein Deutsch ist noch auf A1-Niveau, ich arbeite täglich daran. Englisch beherrsche ich auf muttersprachlichem Niveau. Fachtexte auf Deutsch lese ich schon gut, Schreiben und Sprechen sind die Baustellen.

Über eine Einladung zu einem Gespräch freue ich mich.
Gerald Bosu Ofori
"""),
    "001c3150d1447fed": (
        "adesso SE", "Werkstudent Softwareentwicklung .NET", """Sehr geehrte Damen und Herren,

Ihre Werkstudentenstelle beschreibt den Job, den ich am besten kann: Kundenanwendungen bauen, bei denen Technik und Geschäftsprozess zusammenpassen.

Ich arbeite seit vier Jahren als Software Engineer im Frontend, zuletzt bei Hubtel in Accra. Mein Stack ist TypeScript mit React, Next.js und Nuxt, außerdem habe ich in Java/Groovy-Grails- und ASP.NET-Projekten mitgearbeitet. Bei Enscript Solutions habe ich eine Angular-SPA gegen eine alte Multi-Page-Anwendung getauscht, inklusive Nebular-Integration, und später eine React/Nodejs-Plattform für Fondsmanager gepflegt. Der Umgang mit .NET-nahe Umgebungen ist mir also nicht fremd, auch wenn mein Schwerpunkt JavaScript liegt.

Was neben dem Code zählt: Testkultur. Ich schreibe Vitest- und React-Testing-Library-Tests, wo andere sie überspringen, und dokumentiere, was ich baue.

Seit Oktober studiere ich M.Sc. Embedded Systems an der TU Chemnitz, die Stelle in Leipzig ist damit gut zu verbinden. Deutsch spreche ich aktuell auf A1, ich lerne intensiv; Englisch ist meine Arbeitssprache.

Wenn Sie einen Werkstudenten suchen, der Web-Frontends sicher beherrscht und .NET kennenlernt, freue ich mich über ein Gespräch.

Gerald Bosu Ofori
"""),
    "adedde61f0ada009": (
        "Ferroelectric Memory Company", "Working Student IT", """Sehr geehrte Damen und Herren,

IT-Betrieb in einem Hardware-Unternehmen ist eine Umgebung, in der ich schnell nützlich werde, weil ich beides kenne: die Supportseite eines Betriebes und die Entwicklerseite dahinter.

Bei Hubtel in Accra habe ich vier Jahre produktive Web-Systeme gebaut und betrieben, mit allem, was dazugehört: Nutzerprobleme reproduzieren, Berechtigungen debuggen, Deployments absichern, Onboarding von Kolleginnen und Kollegen auf unsere Tools. AWS Certified Cloud Practitioner abdeckt den Cloud-Teil, bei der Citizen Web App habe ich selbst Server-Proxies und Rate-Limiting gesetzt, also auch die Infrastruktur, hinter der ein IT-Team später den Support macht.

Gleichzeitig studiere ich seit Oktober M.Sc. Embedded Systems an der TU Chemnitz. FeRAM ist genau das Feld, das mich zieht: Speicherhardware, die aus der Forschung in die Anwendung kommt. Ein Werkstudentenjob in Ihrer IT gibt mir beides, Praxis im Betrieb und Nähe zu einem Unternehmen, dessen Produkt ich spannend finde.

Deutsch: A1, täglich Lernroutine. Englisch: fließend, Arbeitssprache in allen meinen Projekten.

Ich freue mich, von Ihnen zu hören.

Gerald Bosu Ofori
"""),
}


def main() -> int:
    conn = db()
    for jid, (company, role, text) in LETTERS.items():
        row = conn.execute("SELECT id FROM jobs WHERE id=?", (jid,)).fetchone()
        if not row:
            print("skip (no job):", jid); continue
        md, pdf = save_letter(company, role, text.strip(), ident, job_id=jid)
        conn.execute("UPDATE jobs SET cover_letter_path=? WHERE id=?", (str(pdf), jid))
        print(f"letter: {pdf.name}  ({len(text.split())} words)")
    conn.commit()
    return 0


if __name__ == "__main__":
    sys.exit(main())

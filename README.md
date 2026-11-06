# Job Hunt

Werkstudent application command center for Gerald Ofori — discovers, scores, and
tracks working-student roles (Frontend / Embedded) in Chemnitz, Leipzig,
Dresden, and remote Germany, plus recruiter discovery for cold outreach.

Replaces the legacy Python automation (kept read-only in `python/legacy/`).

## Stack

- Next.js 16 (App Router, TypeScript strict) + Tailwind v4 + shadcn/ui
- SQLite via Drizzle ORM (`data/jobhunt.db`)
- Background workers in `workers/` (Node, tsx): sourcing, matching, contacts, briefs
- Human-in-the-loop: nothing is submitted automatically

## Pages

| Page    | What it shows                                             |
|---------|-----------------------------------------------------------|
| `/`     | Pipeline stats, status/source charts, top shortlisted     |
| `/queue`| Shortlisted jobs → Mark applied / Dismiss                 |
| `/jobs` | Full job table with search + filters                      |
| `/companies` | Companies with domains, job and contact counts       |
| `/contacts`  | Recruiter/HR contacts with verification status        |
| `/outreach`  | Cold email drafts (copy → send from your own inbox)   |
| `/runs` | History of discovery/contact runs                         |

## Daily operation

```
npm run daily            # discovery → ATS boards → brief → notification
```

Install the 10:00 launchd schedule once:

```
mkdir -p logs
cp workers/com.gerald.jobhunt.daily.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gerald.jobhunt.daily.plist
```

## Manual commands

```
npm run dev              # dashboard on :3000 (or PORT=? your choice)
npm run discovery        # JobSpy sweep (LinkedIn + Indeed) with scoring
npm run ats:run          # fetch ATS career pages (Greenhouse, Lever, Personio, …)
npm run stepstone:run    # Stepstone sweep (opens a headful browser window)
npm run linkedin:login   # one-time manual LinkedIn login (persists session)
npm run contacts:run     # recruiter discovery (domains → impressum → Hunter verify)
npm run brief            # write today's brief only
npm run db:migrate       # apply schema migrations
npm run db:studio        # Drizzle Studio over the SQLite DB
```

## Recruiter email pipeline

1. `applyMinedDomains()` mines company domains from job descriptions
2. Impressum pages are parsed for publicly listed HR contacts
3. LinkedIn people search (logged-in session) finds Talent Acquisition staff
4. Hunter.io finds + verifies addresses (budget-capped per run, 50 searches/month free)
5. Apollo enriches company profiles (free tier: company data only)

## Quality gates

```
npm run lint         # biome check — must be clean
npm run type-check   # tsc strict
npm run test         # vitest (25 tests)
npm run build
```

## Local secrets

`.env.local` (gitignored) holds `DATABASE_URL`, `HUNTER_API_KEY`,
`APOLLO_API_KEY`. Personal documents (`documents/`, `resume/`,
`cover_letters/`), browser sessions (`browser-profile/`), and the database
(`data/`) are gitignored — the repo contains code only.

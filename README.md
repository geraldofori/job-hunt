# Job Hunt

Werkstudent application command center for Gerald Ofori — discovers, scores, and
tracks working-student roles (Frontend / Embedded) in Chemnitz, Leipzig,
Dresden, and remote Germany, plus recruiter discovery for cold outreach.

Replaces the legacy Python automation (kept read-only in `python/legacy/`).

## Stack

- Next.js 16 (App Router, TypeScript strict) + Tailwind v4 + shadcn/ui
- SQLite via Drizzle ORM (`data/jobhunt.db`)
- Background workers in `workers/` (Node): job sourcing, matching, contact discovery, email drafting
- Human-in-the-loop: nothing is submitted automatically

## Daily operation (after full migration)

```
npm run daily        # discovery → scoring → brief (scheduled via launchd at 10:00)
npm run dev          # dashboard at http://localhost:3000
```

## Quality gates

```
npm run lint         # biome check — must be clean
npm run type-check   # tsc strict
npm run build
```

## Local secrets

`.env.local` (gitignored) holds `DATABASE_URL`, `HUNTER_API_KEY`,
`APOLLO_API_KEY`. Personal documents (`documents/`, `resume/`,
`cover_letters/`), the browser session (`browser-profile/`), and the database
(`data/`) are gitignored — the repo contains code only.

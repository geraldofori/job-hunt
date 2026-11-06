import Database from "better-sqlite3";
import { sql } from "drizzle-orm";

import { db, sqlite } from "../src/server/db";
import { companies, jobs } from "../src/server/db/schema";

const LEGACY_DB_PATH = process.argv[2] ?? "./data/legacy-jobs.db";

type LegacyRow = {
  id: string;
  site: string;
  title: string;
  company: string;
  location: string | null;
  work_model: string | null;
  job_url: string | null;
  description: string | null;
  language: string | null;
  date_posted: string | null;
  easy_apply: number | null;
  score: number | null;
  status: string | null;
  first_seen: string | null;
  applied_at: string | null;
  cover_letter_path: string | null;
  notes: string | null;
};

async function main() {
  const legacy = new Database(LEGACY_DB_PATH, { readonly: true });
  const rows = legacy
    .prepare("SELECT * FROM jobs")
    .all() as unknown as LegacyRow[];

  const existingIds = new Set(
    db.select({ id: jobs.id }).from(jobs).all().map((j) => j.id),
  );

  const companyNames = [
    ...new Set(rows.map((r) => r.company).filter((c) => c.trim().length > 0)),
  ];
  const existingCompanies = new Set(
    db.select({ name: companies.name }).from(companies).all().map((c) => c.name),
  );
  const newCompanies = companyNames.filter((name) => !existingCompanies.has(name));

  sqlite.transaction(() => {
    for (const name of newCompanies) {
      db.insert(companies)
        .values({ name })
        .onConflictDoNothing()
        .run();
    }
  })();

  const companyByName = new Map(
    db.select({ id: companies.id, name: companies.name }).from(companies).all().map((c) => [c.name, c.id]),
  );

  const toInsert = rows
    .filter((row) => !existingIds.has(row.id))
    .map((row) => ({
      id: row.id,
      companyId: companyByName.get(row.company) ?? null,
      site: row.site,
      title: row.title,
      company: row.company,
      location: row.location,
      workModel: row.work_model,
      jobUrl: row.job_url,
      description: row.description,
      language: row.language ?? "unknown",
      datePosted: row.date_posted,
      easyApply: row.easy_apply === 1,
      score: row.score,
      status: row.status ?? "new",
      firstSeen: row.first_seen ?? sql`CURRENT_TIMESTAMP` as unknown as string,
      appliedAt: row.applied_at,
      coverLetterPath: row.cover_letter_path,
      notes: row.notes,
    }));

  const batchSize = 500;
  let inserted = 0;
  for (let i = 0; i < toInsert.length; i += batchSize) {
    const batch = toInsert.slice(i, i + batchSize);
    sqlite.transaction(() => {
      db.insert(jobs).values(batch).onConflictDoNothing().run();
    })();
    inserted += batch.length;
  }

  legacy.close();

  console.log(
    `Legacy import complete: ${inserted} jobs inserted (${rows.length - inserted} already present), ${newCompanies.length} companies created.`,
  );
}

main().catch((error) => {
  console.error("Legacy import failed:", error);
  process.exit(1);
});

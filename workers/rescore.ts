import { eq, inArray } from "drizzle-orm";

import { db, sqlite } from "@/server/db";
import { jobs } from "@/server/db/schema";
import { evaluateJob } from "@/server/matching/matcher";

const RESCORABLE_STATUSES = ["new", "shortlisted", "skipped"] as const;

function main() {
  const rows = db
    .select({
      id: jobs.id,
      title: jobs.title,
      description: jobs.description,
      company: jobs.company,
      location: jobs.location,
      workModel: jobs.workModel,
      language: jobs.language,
    })
    .from(jobs)
    .where(inArray(jobs.status, [...RESCORABLE_STATUSES]))
    .all();

  let shortlisted = 0;
  let skipped = 0;
  const updates: { id: string; score: number | null; status: string; workModel: string; language: string; notes: string | null }[] = [];

  for (const row of rows) {
    const verdict = evaluateJob({
      title: row.title,
      description: row.description,
      company: row.company,
      location: row.location,
      workModel: row.workModel,
      language: row.language,
      easyApply: false,
    });

    if (verdict.accepted) shortlisted += 1;
    else skipped += 1;

    updates.push({
      id: row.id,
      score: verdict.score,
      status: verdict.accepted ? "shortlisted" : "skipped",
      workModel: verdict.workModel,
      language: verdict.language,
      notes: verdict.reason ?? null,
    });
  }

  const batchSize = 300;
  for (let i = 0; i < updates.length; i += batchSize) {
    const batch = updates.slice(i, i + batchSize);
    sqlite.transaction(() => {
      for (const update of batch) {
        db.update(jobs)
          .set({
            score: update.score,
            status: update.status,
            workModel: update.workModel,
            language: update.language,
            notes: update.notes,
          })
          .where(eq(jobs.id, update.id))
          .run();
      }
    })();
  }

  console.log(
    `Rescore complete: ${rows.length} evaluated, ${shortlisted} shortlisted, ${skipped} skipped.`,
  );
}

main();

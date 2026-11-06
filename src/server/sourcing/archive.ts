import { inArray } from "drizzle-orm";

import { db } from "@/server/db";
import { ARCHIVE_AFTER_DAYS, jobs } from "@/server/db/schema";

export type ArchiveResult = {
  checked: number;
  archived: number;
};

export async function archiveStaleJobs(
  afterDays: number = ARCHIVE_AFTER_DAYS,
): Promise<ArchiveResult> {
  const cutoff = new Date(Date.now() - afterDays * 86_400_000)
    .toISOString()
    .slice(0, 10);

  const stale = db
    .select({
      id: jobs.id,
      datePosted: jobs.datePosted,
      firstSeen: jobs.firstSeen,
    })
    .from(jobs)
    .where(inArray(jobs.status, ["shortlisted", "new"]))
    .all();

  const staleIds = stale
    .filter((job) => {
      const effectiveDate = job.datePosted || job.firstSeen?.slice(0, 10) || "";
      if (!effectiveDate) return true;
      return effectiveDate < cutoff;
    })
    .map((job) => job.id);

  if (staleIds.length === 0) {
    return { checked: stale.length, archived: 0 };
  }

  const batchSize = 300;
  for (let i = 0; i < staleIds.length; i += batchSize) {
    const batch = staleIds.slice(i, i + batchSize);
    db.update(jobs)
      .set({
        status: "archived",
        notes: `auto-archived: older than ${afterDays} days`,
      })
      .where(inArray(jobs.id, batch))
      .run();
  }

  return { checked: stale.length, archived: staleIds.length };
}

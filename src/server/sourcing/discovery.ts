import { eq } from "drizzle-orm";

import { db, sqlite } from "@/server/db";
import { companies, jobs, runs } from "@/server/db/schema";
import { evaluateJob } from "@/server/matching/matcher";
import {
  fetchViaJobSpy,
  type JobSpyConfig,
  jobIdOf,
  siteOf,
} from "@/server/sourcing/jobspy-bridge";

export const SEARCH_CONFIG: JobSpyConfig = {
  queries: [
    "Werkstudent Softwareentwicklung",
    "Werkstudent Frontend",
    "Werkstudent Webentwicklung",
    "Working Student Software Engineer",
    "Working Student Frontend Developer",
    "Werkstudent Embedded",
    "Working Student Embedded Software",
    "Werkstudent Informatik",
  ],
  location: "Germany",
  hoursOld: 168,
  resultsPerQuery: 25,
  distanceKm: 50,
};

export type DiscoveryResult = {
  fetched: number;
  inserted: number;
  shortlisted: number;
  skipped: number;
};

export async function runDiscovery(
  config: JobSpyConfig = SEARCH_CONFIG,
): Promise<DiscoveryResult> {
  const run = db
    .insert(runs)
    .values({
      type: "discovery",
      sourceCounts: JSON.stringify({ queries: config.queries.length }),
    })
    .returning({ id: runs.id })
    .get();

  const result: DiscoveryResult = {
    fetched: 0,
    inserted: 0,
    shortlisted: 0,
    skipped: 0,
  };
  let runError: string | null = null;

  try {
    const { records } = await fetchViaJobSpy(config);
    result.fetched = records.length;

    const existingIds = new Set(
      db
        .select({ id: jobs.id })
        .from(jobs)
        .all()
        .map((j) => j.id),
    );
    const companyNames = new Set(
      db
        .select({ name: companies.name })
        .from(companies)
        .all()
        .map((c) => c.name.toLowerCase()),
    );

    const insertBatch: (typeof jobs.$inferInsert)[] = [];

    for (const record of records) {
      if (!record.title || !record.job_url) continue;
      const site = siteOf(record);
      const url = record.job_url_direct || record.job_url;
      const id = jobIdOf(site, url);
      if (existingIds.has(id)) continue;

      const verdict = evaluateJob({
        title: record.title,
        description: record.description ?? null,
        company: record.company ?? "",
        location: record.location ?? null,
        workModel: record.is_remote ? "remote" : null,
        language: null,
        easyApply: false,
      });

      result.skipped += verdict.accepted ? 0 : 1;
      if (verdict.accepted) result.shortlisted += 1;

      const companyName = record.company ?? "Unknown";
      if (
        companyName !== "Unknown" &&
        !companyNames.has(companyName.toLowerCase())
      ) {
        db.insert(companies)
          .values({ name: companyName })
          .onConflictDoNothing()
          .run();
        companyNames.add(companyName.toLowerCase());
      }
      const companyId =
        db
          .select({ id: companies.id })
          .from(companies)
          .where(eq(companies.name, companyName))
          .get()?.id ?? null;

      insertBatch.push({
        id,
        companyId,
        site,
        title: record.title,
        company: companyName,
        location: record.location ?? null,
        workModel: verdict.workModel,
        jobUrl: url,
        description: record.description ?? null,
        language: verdict.language,
        datePosted: record.date_posted ?? null,
        score: verdict.score,
        status: verdict.accepted ? "shortlisted" : "skipped",
        notes: verdict.reason ?? null,
      });
      existingIds.add(id);
      result.inserted += 1;
    }

    const batchSize = 200;
    for (let i = 0; i < insertBatch.length; i += batchSize) {
      const batch = insertBatch.slice(i, i + batchSize);
      sqlite.transaction(() => {
        db.insert(jobs).values(batch).onConflictDoNothing().run();
      })();
    }
  } catch (error) {
    runError = error instanceof Error ? error.message : String(error);
    throw error;
  } finally {
    db.update(runs)
      .set({
        finishedAt: new Date().toISOString(),
        newJobs: result.inserted,
        sourceCounts: JSON.stringify(result),
        error: runError,
      })
      .where(eq(runs.id, run.id))
      .run();
  }

  return result;
}

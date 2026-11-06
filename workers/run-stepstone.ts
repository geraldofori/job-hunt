import path from "node:path";
import { eq } from "drizzle-orm";

import { db, sqlite } from "@/server/db";
import { jobs, runs } from "@/server/db/schema";
import { evaluateJob } from "@/server/matching/matcher";
import { jobIdOf } from "@/server/sourcing/jobspy-bridge";
import {
  STEPSTONE_DEFAULTS,
  type StepstoneJobCard,
  scrapeStepstone,
  withStepstoneSession,
} from "@/server/sourcing/stepstone";

function profileDir(): string {
  return path.resolve("browser-profile/stepstone");
}

async function ingest(cards: StepstoneJobCard[]) {
  const existingIds = new Set(
    db
      .select({ id: jobs.id })
      .from(jobs)
      .all()
      .map((j) => j.id),
  );

  let inserted = 0;
  let shortlisted = 0;
  let skipped = 0;
  const batch: (typeof jobs.$inferInsert)[] = [];

  for (const card of cards) {
    const id = jobIdOf("stepstone", card.href);
    if (existingIds.has(id)) continue;

    const verdict = evaluateJob({
      title: card.title,
      description: null,
      company: card.company,
      location: card.location,
      workModel: null,
      language: null,
      easyApply: false,
    });

    inserted += 1;
    if (verdict.accepted) shortlisted += 1;
    else skipped += 1;

    batch.push({
      id,
      site: "stepstone",
      title: card.title,
      company: card.company || "Unknown",
      location: card.location || null,
      workModel: verdict.workModel,
      jobUrl: card.href,
      description: null,
      language: verdict.language,
      score: verdict.score,
      status: verdict.accepted ? "shortlisted" : "skipped",
      notes: verdict.reason ?? null,
    });
  }

  const batchSize = 100;
  for (let i = 0; i < batch.length; i += batchSize) {
    const chunk = batch.slice(i, i + batchSize);
    sqlite.transaction(() => {
      db.insert(jobs).values(chunk).onConflictDoNothing().run();
    })();
  }

  return { inserted, shortlisted, skipped };
}

async function main() {
  const run = db
    .insert(runs)
    .values({
      type: "discovery",
      sourceCounts: JSON.stringify({ source: "stepstone" }),
    })
    .returning({ id: runs.id })
    .get();

  let error: string | null = null;
  try {
    const cards = await withStepstoneSession(profileDir(), (page) =>
      scrapeStepstone(page, STEPSTONE_DEFAULTS),
    );
    console.log(`Scraped ${cards.length} unique cards.`);
    const result = await ingest(cards);
    console.log(
      `Ingested: ${result.inserted} new, ${result.shortlisted} shortlisted, ${result.skipped} skipped.`,
    );
  } catch (thrown) {
    error = thrown instanceof Error ? thrown.message : String(thrown);
    throw thrown;
  } finally {
    db.update(runs)
      .set({
        finishedAt: new Date().toISOString(),
        sourceCounts: JSON.stringify({ source: "stepstone", error }),
        error,
      })
      .where(eq(runs.id, run.id))
      .run();
  }
}

main().catch((error) => {
  console.error("Stepstone run failed:", error);
  process.exit(1);
});

import { count, desc, eq, gte } from "drizzle-orm";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import { db } from "@/server/db";
import { contacts, jobs, outreachMessages, runs } from "@/server/db/schema";
import { scanResponses } from "@/server/monitoring/gmail";

export type Brief = {
  date: string;
  markdown: string;
};

export async function buildBrief(): Promise<Brief> {
  const today = new Date().toISOString().slice(0, 10);
  const weekAgo = new Date(Date.now() - 7 * 86_400_000).toISOString();

  const jobCounts = db
    .select({ newThisWeek: count() })
    .from(jobs)
    .where(gte(jobs.firstSeen, weekAgo))
    .get();

  const shortlisted = db
    .select({ id: jobs.id, title: jobs.title, company: jobs.company, score: jobs.score })
    .from(jobs)
    .where(eq(jobs.status, "shortlisted"))
    .orderBy(desc(jobs.score))
    .limit(5)
    .all();

  const recentRuns = db
    .select()
    .from(runs)
    .orderBy(desc(runs.id))
    .limit(5)
    .all();

  const draftCount = db
    .select({ value: count() })
    .from(outreachMessages)
    .where(eq(outreachMessages.status, "draft"))
    .get();

  const contactCount = db.select({ value: count() }).from(contacts).get();

  let gmailSection = "_Gmail scan skipped._\n";
  try {
    const responses = await scanResponses(10);
    gmailSection = responses.length
      ? responses.map((r) => `- **${r.subject}** — ${r.from.split("<")[0].trim()}`).join("\n") + "\n"
      : "_No application responses in the last 7 days._\n";
  } catch (error) {
    gmailSection = `_Gmail scan failed: ${error instanceof Error ? error.message : String(error)}_\n`;
  }

  const markdown = `# Daily brief — ${today}

## Pipeline
- New jobs this week: **${jobCounts?.newThisWeek ?? 0}**
- Top shortlisted right now: **${shortlisted.length}** (see /queue)
- Draft emails waiting: **${draftCount?.value ?? 0}**
- Contacts in CRM: **${contactCount?.value ?? 0}**

## Recent runs
${recentRuns.map((run) => `- ${run.type} #${run.id} — ${run.finishedAt ?? "running"} (${run.sourceCounts ?? "no stats"})`).join("\n")}

## Gmail responses (last 7 days)
${gmailSection}
`;

  await mkdir(path.resolve("data/runs"), { recursive: true });
  await writeFile(path.resolve(`data/runs/${today}_brief.md`), markdown);

  return { date: today, markdown };
}

export async function notify(title: string, message: string): Promise<void> {
  const { execFile } = await import("node:child_process");
  await new Promise<void>((resolve) => {
    execFile("osascript", [
      "-e",
      `display notification ${JSON.stringify(message)} with title ${JSON.stringify(title)}`,
    ], () => resolve());
  });
}

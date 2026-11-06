import { and, avg, count, desc, eq, gte, sql } from "drizzle-orm";

import { db } from "@/server/db";
import { jobs } from "@/server/db/schema";

export type PipelineStats = {
  total: number;
  shortlisted: number;
  applied: number;
  newThisWeek: number;
  avgScore: number;
};

export async function getPipelineStats(): Promise<PipelineStats> {
  const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();

  const [totals] = await db
    .select({
      total: count(),
      shortlisted: sql<number>`SUM(CASE WHEN ${jobs.status} = 'shortlisted' THEN 1 ELSE 0 END)`,
      applied: sql<number>`SUM(CASE WHEN ${jobs.status} = 'applied' THEN 1 ELSE 0 END)`,
      newThisWeek: sql<number>`SUM(CASE WHEN ${jobs.firstSeen} >= ${weekAgo} THEN 1 ELSE 0 END)`,
      avgScore: avg(jobs.score),
    })
    .from(jobs);

  return {
    total: totals?.total ?? 0,
    shortlisted: Number(totals?.shortlisted ?? 0),
    applied: Number(totals?.applied ?? 0),
    newThisWeek: Number(totals?.newThisWeek ?? 0),
    avgScore: Number(totals?.avgScore ?? 0),
  };
}

export type Slice = { label: string; value: number };

export async function getStatusBreakdown(): Promise<Slice[]> {
  const rows = await db
    .select({ label: jobs.status, value: count() })
    .from(jobs)
    .groupBy(jobs.status)
    .orderBy(desc(count()));
  return rows.map((r) => ({ label: r.label ?? "unknown", value: r.value }));
}

export async function getSourceBreakdown(): Promise<Slice[]> {
  const rows = await db
    .select({ label: jobs.site, value: count() })
    .from(jobs)
    .groupBy(jobs.site)
    .orderBy(desc(count()));
  return rows.map((r) => ({ label: r.label ?? "unknown", value: r.value }));
}

export type TopJob = {
  id: string;
  title: string;
  company: string;
  location: string | null;
  score: number | null;
  jobUrl: string | null;
  status: string;
};

export async function getTopJobs(limit = 10): Promise<TopJob[]> {
  return db
    .select({
      id: jobs.id,
      title: jobs.title,
      company: jobs.company,
      location: jobs.location,
      score: jobs.score,
      jobUrl: jobs.jobUrl,
      status: jobs.status,
    })
    .from(jobs)
    .where(and(eq(jobs.status, "shortlisted"), gte(jobs.score, 1)))
    .orderBy(desc(jobs.score))
    .limit(limit);
}

import { and, count, desc, eq, gte, ilike, or, type SQL } from "drizzle-orm";

import { db } from "@/server/db";
import { jobStatus, jobs } from "@/server/db/schema";

export type JobRow = {
  id: string;
  site: string;
  title: string;
  company: string;
  location: string | null;
  workModel: string | null;
  jobUrl: string | null;
  score: number | null;
  status: string;
  datePosted: string | null;
  firstSeen: string;
};

export type JobFilters = {
  status?: string;
  site?: string;
  minScore?: number;
  search?: string;
  page?: number;
};

const PAGE_SIZE = 25;

function buildWhere(filters: JobFilters): SQL | undefined {
  const conditions: SQL[] = [];

  if (filters.status && jobStatus.includes(filters.status as never)) {
    conditions.push(eq(jobs.status, filters.status));
  }
  if (filters.site) {
    conditions.push(eq(jobs.site, filters.site));
  }
  if (filters.minScore !== undefined) {
    conditions.push(gte(jobs.score, filters.minScore));
  }
  if (filters.search) {
    const term = `%${filters.search}%`;
    conditions.push(
      or(ilike(jobs.title, term), ilike(jobs.company, term)) as SQL,
    );
  }

  return conditions.length > 0 ? and(...conditions) : undefined;
}

export async function getJobs(filters: JobFilters) {
  const where = buildWhere(filters);
  const page = Math.max(1, filters.page ?? 1);

  const rows = await db
    .select({
      id: jobs.id,
      site: jobs.site,
      title: jobs.title,
      company: jobs.company,
      location: jobs.location,
      workModel: jobs.workModel,
      jobUrl: jobs.jobUrl,
      score: jobs.score,
      status: jobs.status,
      datePosted: jobs.datePosted,
      firstSeen: jobs.firstSeen,
    })
    .from(jobs)
    .where(where)
    .orderBy(desc(jobs.score), desc(jobs.firstSeen))
    .limit(PAGE_SIZE)
    .offset((page - 1) * PAGE_SIZE);

  const [{ total }] = await db
    .select({ total: count() })
    .from(jobs)
    .where(where);

  return {
    rows,
    total,
    page,
    pageSize: PAGE_SIZE,
    totalPages: Math.max(1, Math.ceil(total / PAGE_SIZE)),
  };
}

export async function getSites(): Promise<string[]> {
  const rows = await db
    .select({ site: jobs.site })
    .from(jobs)
    .groupBy(jobs.site)
    .orderBy(jobs.site);
  return rows.map((r) => r.site);
}

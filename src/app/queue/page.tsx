import { and, desc, eq } from "drizzle-orm";

import { QueueRow } from "@/features/queue/components/QueueRow";
import { db } from "@/server/db";
import { jobs } from "@/server/db/schema";

export const dynamic = "force-dynamic";

export default async function QueuePage() {
  const queue = db
    .select({
      id: jobs.id,
      title: jobs.title,
      company: jobs.company,
      location: jobs.location,
      workModel: jobs.workModel,
      jobUrl: jobs.jobUrl,
      score: jobs.score,
      firstSeen: jobs.firstSeen,
    })
    .from(jobs)
    .where(and(eq(jobs.status, "shortlisted")))
    .orderBy(desc(jobs.score))
    .limit(50)
    .all();

  const applied = db
    .select({
      id: jobs.id,
      title: jobs.title,
      company: jobs.company,
      appliedAt: jobs.appliedAt,
    })
    .from(jobs)
    .where(eq(jobs.status, "applied"))
    .orderBy(desc(jobs.appliedAt))
    .limit(10)
    .all();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Application queue
        </h1>
        <p className="text-sm text-muted-foreground">
          Shortlisted jobs waiting for your decision — nothing is submitted
          automatically.
        </p>
      </div>

      <ul className="flex flex-col gap-3">
        {queue.map((job) => (
          <QueueRow key={job.id} job={job} />
        ))}
        {queue.length === 0 ? (
          <li className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
            Queue is empty — run discovery to refill it.
          </li>
        ) : null}
      </ul>

      {applied.length > 0 ? (
        <div className="rounded-lg border bg-card">
          <div className="border-b px-4 py-3">
            <h2 className="text-sm font-medium">Recently applied</h2>
          </div>
          <ul className="divide-y">
            {applied.map((job) => (
              <li
                key={job.id}
                className="flex items-center justify-between px-4 py-2.5"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm">{job.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {job.company}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground">
                  {job.appliedAt
                    ? new Date(job.appliedAt).toLocaleDateString("en-GB")
                    : "—"}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

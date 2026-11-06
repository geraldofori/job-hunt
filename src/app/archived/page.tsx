import { desc, eq } from "drizzle-orm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { deleteJobAction, restoreJobAction } from "@/features/archive/actions";
import { db } from "@/server/db";
import { jobs } from "@/server/db/schema";

export const dynamic = "force-dynamic";

export default async function ArchivedPage() {
  const archived = db
    .select({
      id: jobs.id,
      title: jobs.title,
      company: jobs.company,
      location: jobs.location,
      workModel: jobs.workModel,
      jobUrl: jobs.jobUrl,
      score: jobs.score,
      datePosted: jobs.datePosted,
      firstSeen: jobs.firstSeen,
      notes: jobs.notes,
      status: jobs.status,
    })
    .from(jobs)
    .where(eq(jobs.status, "archived"))
    .orderBy(desc(jobs.score))
    .limit(100)
    .all();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Archived jobs</h1>
        <p className="text-sm text-muted-foreground">
          Postings no longer accepting applications — auto-archived after 45
          days, or archived by hand from the queue. Restoring sends a job back
          to the queue.
        </p>
      </div>

      <ul className="flex flex-col gap-2">
        {archived.map((job) => (
          <li
            key={job.id}
            className="flex flex-col gap-2 rounded-lg border bg-card p-3 sm:flex-row sm:items-center"
          >
            <Badge
              variant="secondary"
              className="w-10 justify-center font-mono"
            >
              {job.score === null ? "—" : Math.round(job.score)}
            </Badge>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm">{job.title}</p>
              <p className="truncate text-xs text-muted-foreground">
                {job.company} · {job.location ?? "—"} · seen{" "}
                {(job.datePosted ?? job.firstSeen ?? "").slice(0, 10)}
                {job.notes ? ` · ${job.notes}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {job.jobUrl ? (
                <a
                  href={job.jobUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-muted-foreground underline hover:text-foreground"
                >
                  posting
                </a>
              ) : null}
              <form action={restoreJobAction}>
                <input type="hidden" name="jobId" value={job.id} />
                <Button type="submit" variant="outline" size="sm">
                  Restore
                </Button>
              </form>
              <form action={deleteJobAction}>
                <input type="hidden" name="jobId" value={job.id} />
                <Button type="submit" variant="ghost" size="sm">
                  Delete
                </Button>
              </form>
            </div>
          </li>
        ))}
        {archived.length === 0 ? (
          <li className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
            Nothing archived yet.
          </li>
        ) : null}
      </ul>
    </div>
  );
}

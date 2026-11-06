import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

import { setJobStatusAction } from "../actions";

export type QueueJob = {
  id: string;
  title: string;
  company: string;
  location: string | null;
  workModel: string | null;
  jobUrl: string | null;
  score: number | null;
  firstSeen: string;
};

export function QueueRow({ job }: { job: QueueJob }) {
  return (
    <li className="flex flex-col gap-3 rounded-lg border bg-card p-4 sm:flex-row sm:items-center">
      <Badge variant="secondary" className="w-10 justify-center font-mono">
        {job.score === null ? "—" : Math.round(job.score)}
      </Badge>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{job.title}</p>
        <p className="truncate text-xs text-muted-foreground">
          {job.company} · {job.location ?? "—"}
          {job.workModel ? ` · ${job.workModel}` : ""}
        </p>
      </div>

      <div className="flex items-center gap-2">
        {job.jobUrl ? (
          <Button asChild variant="outline" size="sm">
            <a href={job.jobUrl} target="_blank" rel="noreferrer">
              Open <ExternalLink className="size-3.5" />
            </a>
          </Button>
        ) : null}

        <form action={setJobStatusAction} className="flex items-center gap-2">
          <input type="hidden" name="jobId" value={job.id} />
          <input type="hidden" name="status" value="applied" />
          <Button type="submit" size="sm">
            Mark applied
          </Button>
        </form>

        <form action={setJobStatusAction} className="flex items-center gap-2">
          <input type="hidden" name="jobId" value={job.id} />
          <input type="hidden" name="status" value="archived" />
          <input
            type="hidden"
            name="note"
            value="no longer accepting applications"
          />
          <Button type="submit" variant="ghost" size="sm">
            Archive
          </Button>
        </form>

        <form action={setJobStatusAction} className="flex items-center gap-2">
          <input type="hidden" name="jobId" value={job.id} />
          <input type="hidden" name="status" value="skipped" />
          <input type="hidden" name="note" value="dismissed from queue" />
          <Button type="submit" variant="ghost" size="sm">
            Dismiss
          </Button>
        </form>
      </div>
    </li>
  );
}

import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";

import { getTopJobs } from "../queries";

const statusVariant: Record<string, string> = {
  shortlisted: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  applied: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  new: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  skipped: "bg-muted text-muted-foreground",
};

export async function TopJobs() {
  const topJobs = await getTopJobs(10);

  return (
    <div className="rounded-lg border bg-card">
      <div className="border-b px-4 py-3">
        <h2 className="text-sm font-medium">Top shortlisted jobs</h2>
      </div>
      <ul className="divide-y">
        {topJobs.map((job) => (
          <li key={job.id} className="flex items-center gap-3 px-4 py-3">
            <Badge
              variant="secondary"
              className="w-10 justify-center font-mono"
            >
              {Math.round(job.score ?? 0)}
            </Badge>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{job.title}</p>
              <p className="truncate text-xs text-muted-foreground">
                {job.company} · {job.location ?? "—"}
              </p>
            </div>
            <span
              className={`hidden rounded-full px-2 py-0.5 text-xs sm:inline ${
                statusVariant[job.status] ?? statusVariant.skipped
              }`}
            >
              {job.status}
            </span>
            {job.jobUrl ? (
              <a
                href={job.jobUrl}
                target="_blank"
                rel="noreferrer"
                className="text-muted-foreground transition-colors hover:text-foreground"
                aria-label={`Open ${job.title} at ${job.company}`}
              >
                <ExternalLink className="size-4" />
              </a>
            ) : null}
          </li>
        ))}
        {topJobs.length === 0 ? (
          <li className="px-4 py-6 text-center text-sm text-muted-foreground">
            No shortlisted jobs yet.
          </li>
        ) : null}
      </ul>
    </div>
  );
}

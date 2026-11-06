import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { JobRow } from "../queries";

const statusVariant: Record<string, string> = {
  shortlisted: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  applied: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  new: "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  skipped: "bg-muted text-muted-foreground",
  closed: "bg-muted text-muted-foreground",
};

export function JobsTable({ rows }: { rows: JobRow[] }) {
  if (rows.length === 0) {
    return (
      <p className="rounded-lg border bg-card px-4 py-8 text-center text-sm text-muted-foreground">
        No jobs match these filters.
      </p>
    );
  }

  return (
    <div className="rounded-lg border bg-card">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-14">Score</TableHead>
            <TableHead>Title</TableHead>
            <TableHead className="hidden md:table-cell">Company</TableHead>
            <TableHead className="hidden lg:table-cell">Location</TableHead>
            <TableHead>Source</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-10" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((job) => (
            <TableRow key={job.id}>
              <TableCell className="font-mono text-xs">
                {job.score === null ? "—" : Math.round(job.score)}
              </TableCell>
              <TableCell className="max-w-72">
                <p className="truncate font-medium">{job.title}</p>
                <p className="truncate text-xs text-muted-foreground md:hidden">
                  {job.company}
                </p>
              </TableCell>
              <TableCell className="hidden max-w-48 truncate md:table-cell">
                {job.company}
              </TableCell>
              <TableCell className="hidden max-w-40 truncate text-muted-foreground lg:table-cell">
                {job.location ?? "—"}
              </TableCell>
              <TableCell>
                <Badge variant="outline">{job.site}</Badge>
              </TableCell>
              <TableCell>
                <span
                  className={`rounded-full px-2 py-0.5 text-xs ${
                    statusVariant[job.status] ?? statusVariant.skipped
                  }`}
                >
                  {job.status}
                </span>
              </TableCell>
              <TableCell>
                {job.jobUrl ? (
                  <a
                    href={job.jobUrl}
                    target="_blank"
                    rel="noreferrer"
                    aria-label={`Open ${job.title} at ${job.company}`}
                    className="text-muted-foreground transition-colors hover:text-foreground"
                  >
                    <ExternalLink className="size-4" />
                  </a>
                ) : null}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

import { desc } from "drizzle-orm";

import { db } from "@/server/db";
import { runs } from "@/server/db/schema";

export const dynamic = "force-dynamic";

export default async function RunsPage() {
  const recent = db.select().from(runs).orderBy(desc(runs.id)).limit(20).all();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Runs</h1>
        <p className="text-sm text-muted-foreground">
          History of discovery and contact runs (latest 20).
        </p>
      </div>

      <div className="rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">ID</th>
              <th className="px-4 py-2.5 font-medium">Type</th>
              <th className="px-4 py-2.5 font-medium">Started</th>
              <th className="px-4 py-2.5 font-medium">Finished</th>
              <th className="px-4 py-2.5 font-medium">New</th>
              <th className="px-4 py-2.5 font-medium">Stats / errors</th>
            </tr>
          </thead>
          <tbody>
            {recent.map((run) => (
              <tr key={run.id} className="border-b last:border-0">
                <td className="px-4 py-2.5 font-mono text-xs">{run.id}</td>
                <td className="px-4 py-2.5">{run.type}</td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">
                  {run.startedAt}
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">
                  {run.finishedAt ?? "—"}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">
                  {run.newJobs ?? run.newContacts ?? 0}
                </td>
                <td className="max-w-80 truncate px-4 py-2.5 text-xs text-muted-foreground">
                  {run.error ?? run.sourceCounts ?? "—"}
                </td>
              </tr>
            ))}
            {recent.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No runs recorded yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

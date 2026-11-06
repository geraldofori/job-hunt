import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import { BreakdownBarChart } from "@/features/dashboard/components/BreakdownBarChart";
import { StatCard } from "@/features/dashboard/components/StatCard";
import { TopJobs } from "@/features/dashboard/components/TopJobs";
import {
  getPipelineStats,
  getSourceBreakdown,
  getStatusBreakdown,
} from "@/features/dashboard/queries";

export const dynamic = "force-dynamic";

export default async function DashboardPage() {
  const [stats, statusSlices, sourceSlices] = await Promise.all([
    getPipelineStats(),
    getStatusBreakdown(),
    getSourceBreakdown(),
  ]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Pipeline overview across all sources.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Total jobs" value={stats.total} />
        <StatCard label="Shortlisted" value={stats.shortlisted} />
        <StatCard label="Applied" value={stats.applied} />
        <StatCard label="New this week" value={stats.newThisWeek} />
        <StatCard label="Avg score" value={stats.avgScore.toFixed(1)} />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Jobs by status</CardTitle>
          </CardHeader>
          <CardContent>
            <BreakdownBarChart data={statusSlices} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle className="text-sm">Jobs by source</CardTitle>
          </CardHeader>
          <CardContent>
            <BreakdownBarChart data={sourceSlices} />
          </CardContent>
        </Card>
      </div>

      <TopJobs />
    </div>
  );
}

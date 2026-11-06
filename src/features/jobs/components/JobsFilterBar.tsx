import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { jobStatus } from "@/server/db/schema";

interface JobsFilterBarProps {
  sites: string[];
  current: {
    status?: string;
    site?: string;
    search?: string;
    minScore?: string;
  };
}

export function JobsFilterBar({ sites, current }: JobsFilterBarProps) {
  return (
    <form method="get" className="flex flex-wrap items-center gap-2">
      <div className="relative min-w-56 flex-1">
        <Search className="absolute top-2.5 left-2.5 size-4 text-muted-foreground" />
        <Input
          name="search"
          placeholder="Search title or company…"
          defaultValue={current.search ?? ""}
          className="pl-8"
        />
      </div>

      <select
        name="status"
        defaultValue={current.status ?? ""}
        className="h-9 rounded-md border bg-background px-3 text-sm"
        aria-label="Filter by status"
      >
        <option value="">All statuses</option>
        {jobStatus.map((status) => (
          <option key={status} value={status}>
            {status}
          </option>
        ))}
      </select>

      <select
        name="site"
        defaultValue={current.site ?? ""}
        className="h-9 rounded-md border bg-background px-3 text-sm"
        aria-label="Filter by source"
      >
        <option value="">All sources</option>
        {sites.map((site) => (
          <option key={site} value={site}>
            {site}
          </option>
        ))}
      </select>

      <select
        name="minScore"
        defaultValue={current.minScore ?? ""}
        className="h-9 rounded-md border bg-background px-3 text-sm"
        aria-label="Minimum score"
      >
        <option value="">Any score</option>
        <option value="5">Score ≥ 5</option>
        <option value="10">Score ≥ 10</option>
        <option value="15">Score ≥ 15</option>
        <option value="20">Score ≥ 20</option>
      </select>

      <Button type="submit" size="sm" className="h-9">
        Apply
      </Button>
    </form>
  );
}

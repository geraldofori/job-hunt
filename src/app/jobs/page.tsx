import { JobsFilterBar } from "@/features/jobs/components/JobsFilterBar";
import { JobsTable } from "@/features/jobs/components/JobsTable";
import { getJobs, getSites } from "@/features/jobs/queries";

type SearchParams = Promise<{
  status?: string;
  site?: string;
  search?: string;
  minScore?: string;
  page?: string;
}>;

export const dynamic = "force-dynamic";

export default async function JobsPage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  const minScore = params.minScore ? Number(params.minScore) : undefined;
  const page = params.page ? Number(params.page) : 1;

  const [{ rows, total, totalPages }, sites] = await Promise.all([
    getJobs({
      status: params.status || undefined,
      site: params.site || undefined,
      search: params.search || undefined,
      minScore: Number.isFinite(minScore) ? minScore : undefined,
      page,
    }),
    getSites(),
  ]);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Jobs</h1>
        <p className="text-sm text-muted-foreground">
          {total} jobs · page {page} of {totalPages}
        </p>
      </div>

      <JobsFilterBar
        sites={sites}
        current={{
          status: params.status,
          site: params.site,
          search: params.search,
          minScore: params.minScore,
        }}
      />

      <JobsTable rows={rows} />

      <div className="flex items-center justify-end gap-2">
        {page > 1 ? (
          <a
            href={`/jobs?${new URLSearchParams({ ...params, page: String(page - 1) })}`}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Previous
          </a>
        ) : null}
        {page < totalPages ? (
          <a
            href={`/jobs?${new URLSearchParams({ ...params, page: String(page + 1) })}`}
            className="rounded-md border px-3 py-1.5 text-sm hover:bg-muted"
          >
            Next
          </a>
        ) : null}
      </div>
    </div>
  );
}

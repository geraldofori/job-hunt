import { count, desc, eq, isNotNull, sql } from "drizzle-orm";
import { Badge } from "@/components/ui/badge";

import { db } from "@/server/db";
import { companies, contacts, jobs } from "@/server/db/schema";

export const dynamic = "force-dynamic";

export default async function CompaniesPage() {
  const withJobs = db
    .select({
      id: companies.id,
      name: companies.name,
      domain: companies.domain,
      atsProvider: companies.atsProvider,
      jobCount: count(jobs.id),
      shortlisted: sql<number>`SUM(CASE WHEN ${jobs.status} = 'shortlisted' THEN 1 ELSE 0 END)`,
    })
    .from(companies)
    .leftJoin(jobs, eq(jobs.companyId, companies.id))
    .groupBy(companies.id)
    .orderBy(desc(count(jobs.id)))
    .limit(30)
    .all();

  const domainsKnown = db
    .select({ value: count() })
    .from(companies)
    .where(isNotNull(companies.domain))
    .get();

  const contactCounts = db
    .select({ companyId: contacts.companyId, value: count() })
    .from(contacts)
    .groupBy(contacts.companyId)
    .all();
  const contactMap = new Map(
    contactCounts.map((row) => [row.companyId, row.value]),
  );

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Companies</h1>
        <p className="text-sm text-muted-foreground">
          {withJobs.length} most relevant of {domainsKnown?.value ?? 0} with
          discovered domains. Contact discovery targets companies with domains.
        </p>
      </div>

      <div className="rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Company</th>
              <th className="px-4 py-2.5 font-medium">Domain</th>
              <th className="px-4 py-2.5 font-medium">Jobs</th>
              <th className="px-4 py-2.5 font-medium">Shortlisted</th>
              <th className="px-4 py-2.5 font-medium">Contacts</th>
            </tr>
          </thead>
          <tbody>
            {withJobs.map((company) => (
              <tr key={company.id} className="border-b last:border-0">
                <td className="max-w-64 truncate px-4 py-2.5 font-medium">
                  {company.name}
                </td>
                <td className="px-4 py-2.5 text-muted-foreground">
                  {company.domain ? (
                    <Badge variant="outline">{company.domain}</Badge>
                  ) : (
                    "—"
                  )}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">
                  {company.jobCount}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">
                  {Number(company.shortlisted)}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">
                  {contactMap.get(company.id) ?? 0}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

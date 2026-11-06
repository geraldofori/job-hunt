import { desc, eq } from "drizzle-orm";
import { ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";

import { db } from "@/server/db";
import { companies, contacts } from "@/server/db/schema";

export const dynamic = "force-dynamic";

const statusVariant: Record<string, string> = {
  valid: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  invalid: "bg-red-500/15 text-red-700 dark:text-red-400",
  "needs-email": "bg-amber-500/15 text-amber-700 dark:text-amber-400",
  unknown: "bg-muted text-muted-foreground",
};

export default async function ContactsPage() {
  const rows = db
    .select({
      id: contacts.id,
      fullName: contacts.fullName,
      role: contacts.role,
      email: contacts.email,
      emailStatus: contacts.emailStatus,
      source: contacts.source,
      linkedinUrl: contacts.linkedinUrl,
      companyName: companies.name,
    })
    .from(contacts)
    .leftJoin(companies, eq(contacts.companyId, companies.id))
    .orderBy(desc(contacts.id))
    .limit(100)
    .all();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Contacts</h1>
        <p className="text-sm text-muted-foreground">
          Recruiters and HR inboxes for cold outreach ({rows.length} latest).
        </p>
      </div>

      <div className="rounded-lg border bg-card">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left text-xs text-muted-foreground">
              <th className="px-4 py-2.5 font-medium">Name</th>
              <th className="px-4 py-2.5 font-medium">Company</th>
              <th className="px-4 py-2.5 font-medium">Email</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Source</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody>
            {rows.map((contact) => (
              <tr key={contact.id} className="border-b last:border-0">
                <td className="max-w-48 truncate px-4 py-2.5">
                  <p className="truncate font-medium">{contact.fullName}</p>
                  {contact.role ? (
                    <p className="truncate text-xs text-muted-foreground">
                      {contact.role}
                    </p>
                  ) : null}
                </td>
                <td className="max-w-40 truncate px-4 py-2.5">
                  {contact.companyName ?? "—"}
                </td>
                <td className="px-4 py-2.5 font-mono text-xs">
                  {contact.email ?? "—"}
                </td>
                <td className="px-4 py-2.5">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      statusVariant[contact.emailStatus ?? "unknown"] ??
                      statusVariant.unknown
                    }`}
                  >
                    {contact.emailStatus ?? "unknown"}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <Badge variant="outline">{contact.source}</Badge>
                </td>
                <td className="px-4 py-2.5">
                  {contact.linkedinUrl ? (
                    <a
                      href={contact.linkedinUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="text-muted-foreground hover:text-foreground"
                      aria-label={`Open LinkedIn profile of ${contact.fullName}`}
                    >
                      <ExternalLink className="size-4" />
                    </a>
                  ) : null}
                </td>
              </tr>
            ))}
            {rows.length === 0 ? (
              <tr>
                <td
                  colSpan={6}
                  className="px-4 py-8 text-center text-muted-foreground"
                >
                  No contacts yet — run <code>npm run contacts:run</code>.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

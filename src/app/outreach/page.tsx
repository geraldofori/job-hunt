import { eq } from "drizzle-orm";
import Link from "next/link";
import { Button } from "@/components/ui/button";

import { createDraftAction } from "@/features/outreach/actions";
import { db } from "@/server/db";
import { companies, contacts } from "@/server/db/schema";
import { listDrafts } from "@/server/outreach/composer";
import { TEMPLATES } from "@/server/outreach/templates";

export const dynamic = "force-dynamic";

const statusVariant: Record<string, string> = {
  draft: "bg-muted text-muted-foreground",
  sent: "bg-blue-500/15 text-blue-700 dark:text-blue-400",
  replied: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400",
  bounced: "bg-red-500/15 text-red-700 dark:text-red-400",
};

export default async function OutreachPage() {
  const drafts = listDrafts();
  const contactOptions = db
    .select({
      id: contacts.id,
      fullName: contacts.fullName,
      companyName: companies.name,
      email: contacts.email,
    })
    .from(contacts)
    .leftJoin(companies, eq(contacts.companyId, companies.id))
    .all();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Outreach</h1>
        <p className="text-sm text-muted-foreground">
          Cold email drafts — review, edit, copy, then send from your own inbox.
        </p>
      </div>

      <form
        action={createDraftAction}
        className="flex flex-wrap items-center gap-2 rounded-lg border bg-card p-4"
      >
        <select
          name="contactId"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          aria-label="Contact"
        >
          <option value="">— no contact —</option>
          {contactOptions.map((contact) => (
            <option key={contact.id} value={contact.id}>
              {contact.fullName}
              {contact.companyName ? ` · ${contact.companyName}` : ""}
            </option>
          ))}
        </select>
        <select
          name="template"
          className="h-9 rounded-md border bg-background px-3 text-sm"
          aria-label="Template"
        >
          {Object.values(TEMPLATES).map((template) => (
            <option key={template.id} value={template.id}>
              {template.label}
            </option>
          ))}
        </select>
        <Button type="submit" size="sm" className="h-9">
          New draft
        </Button>
      </form>

      <ul className="flex flex-col gap-3">
        {drafts.map((draft) => (
          <li key={draft.id} className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">
                  {draft.subject ?? "(no subject)"}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {draft.contactName ?? "—"} · {draft.companyName ?? "—"}
                </p>
              </div>
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${statusVariant[draft.status] ?? statusVariant.draft}`}
              >
                {draft.status}
              </span>
              <Button asChild variant="outline" size="sm">
                <Link href={`/outreach/${draft.id}`}>Edit</Link>
              </Button>
            </div>
          </li>
        ))}
        {drafts.length === 0 ? (
          <li className="rounded-lg border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
            No drafts yet — create one above.
          </li>
        ) : null}
      </ul>
    </div>
  );
}

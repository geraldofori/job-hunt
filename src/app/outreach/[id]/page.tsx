import Link from "next/link";
import { notFound } from "next/navigation";
import { Button } from "@/components/ui/button";

import { DraftEditor } from "@/features/outreach/components/DraftEditor";
import { getDraft } from "@/server/outreach/composer";

export const dynamic = "force-dynamic";

export default async function DraftPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const draft = getDraft(Number(id));
  if (!draft) notFound();

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            Draft to {draft.contactName ?? "—"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {draft.companyName ?? "—"}
            {draft.jobTitle ? ` · ${draft.jobTitle}` : ""}
          </p>
        </div>
        <Button asChild variant="outline" size="sm">
          <Link href="/outreach">Back</Link>
        </Button>
      </div>

      <DraftEditor
        draft={{
          id: draft.id,
          subject: draft.subject,
          body: draft.body,
          status: draft.status,
        }}
      />
    </div>
  );
}
